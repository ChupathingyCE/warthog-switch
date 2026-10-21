/*
HOST_MEMORY_FILES.C

The game's map cache, kept in the host's memory instead of on the SD card.

The game unpacks each map it plays from maps/ (zlib-packed, about half the
size) into one of its cache files, z:\cache000.map to z:\cache005.map, and
reads the map from there while it plays (source/cache/cache_files_windows.c).
On the card that meant some 730 MB of slot files, a map written to the card
each time a slot took a new one, and every texture and sound the game
streams in read back from it. Here the guest's files of those names
(<save root>/z/cacheNNN.map) are answered from memory: the host's own,
outside the guest's address space below 4 GB, which its allocations need.

A slot is held in pieces of a megabyte, made as the game writes into them,
so it holds about its map's size (a multiplayer map 45 MB, a campaign
level more) rather than the size the game gives the file; a piece never
written reads as zeros. The game's own rules still choose, check and
replace the slots; it truncates a slot before it writes a new map into it
(platform_file_discard, port/linux/src/xbox_files.c), which gives the old
map's pieces back. The slots start empty at each start, so a map is
unpacked again the first time it is played.

host_syscall.c sends the guest's calls on these files here: an open gives
a descriptor of HOST_MEMORY_FILE_DESCRIPTOR and up, which no host file has.
*/

#include "host.h"

#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#define SLOT_COUNT 20
#define PIECE_SIZE (1024UL * 1024UL)
#define OPEN_COUNT 64

struct slot
{
	int exists;
	/* whether the card's file of this name, from a build that kept the
	slots there, has been deleted */
	int card_file_checked;
	unsigned long long size;
	unsigned long piece_count;
	char **pieces;
	struct timespec modified;
};

struct open_file
{
	int used;
	int slot;
	unsigned long long position;
};

static struct slot slots[SLOT_COUNT];
static struct open_file opens[OPEN_COUNT];
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static unsigned long pieces_held;

static unsigned long megabytes_held(void)
{
	return pieces_held * (PIECE_SIZE / (1024 * 1024));
}

int host_memory_file_path(const char *path)
{
	size_t length = path ? strlen(path) : 0;
	const char *name;
	int index;

	/* ".../z/cacheNNN.map" */
	if (length < 15)
		return -1;
	name = path + length - 15;
	if (name[0] != '/' || (name[1] | 0x20) != 'z' || name[2] != '/' || strncasecmp(name + 3, "cache", 5) != 0 ||
		!isdigit((unsigned char)name[8]) || !isdigit((unsigned char)name[9]) ||
		!isdigit((unsigned char)name[10]) || strcasecmp(name + 11, ".map") != 0)
		return -1;
	index = (name[8] - '0') * 100 + (name[9] - '0') * 10 + (name[10] - '0');
	return index < SLOT_COUNT ? index : -1;
}

/* (with the lock held) the card's file of the slot's name, from a build
that kept the slots there, deleted the first time the slot is named */
static void forget_card_file(int index, const char *path)
{
	struct slot *slot = &slots[index];
	int removed;

	if (slot->card_file_checked)
		return;
	slot->card_file_checked = 1;
	host_sd_lock();
	removed = unlink(path) == 0;
	host_sd_unlock();
	if (removed)
		host_logf(HOST_LOG_INFO, "map cache: deleted %s from the card (the map cache is kept in memory)", path);
}

/* (with the lock held) the pieces from first on given back */
static void free_pieces(struct slot *slot, unsigned long first)
{
	unsigned long index;

	for (index = first; index < slot->piece_count; index++)
	{
		if (slot->pieces[index])
		{
			free(slot->pieces[index]);
			slot->pieces[index] = NULL;
			pieces_held--;
		}
	}
}

/* (with the lock held) the slot's size changed: its pieces past the end
given back, and room in its list for the pieces up to it */
static int resize(struct slot *slot, unsigned long long size)
{
	unsigned long count = (unsigned long)((size + PIECE_SIZE - 1) / PIECE_SIZE);

	if (count < slot->piece_count)
	{
		free_pieces(slot, count);
		/* (the piece the end now falls in keeps no bytes past it) */
		if (count && slot->pieces[count - 1] && size % PIECE_SIZE)
			memset(slot->pieces[count - 1] + size % PIECE_SIZE, 0, PIECE_SIZE - size % PIECE_SIZE);
	}
	else if (count > slot->piece_count)
	{
		char **pieces = realloc(slot->pieces, count * sizeof(*pieces));

		if (!pieces)
			return -ENOMEM;
		memset(pieces + slot->piece_count, 0, (count - slot->piece_count) * sizeof(*pieces));
		slot->pieces = pieces;
		slot->piece_count = count;
	}
	slot->size = size;
	return 0;
}

static struct open_file *open_of(int descriptor)
{
	int index = descriptor - HOST_MEMORY_FILE_DESCRIPTOR;

	return index >= 0 && index < OPEN_COUNT && opens[index].used ? &opens[index] : NULL;
}

int host_memory_file_is(int descriptor)
{
	return descriptor >= HOST_MEMORY_FILE_DESCRIPTOR && descriptor < HOST_MEMORY_FILE_DESCRIPTOR + OPEN_COUNT;
}

int host_memory_file_open(int index, const char *path, int flags)
{
	struct slot *slot = &slots[index];
	int open_index;
	int result = 0;

	pthread_mutex_lock(&lock);
	forget_card_file(index, path);
	if (!slot->exists && !(flags & O_CREAT))
		result = -ENOENT;
	else if (slot->exists && (flags & O_CREAT) && (flags & O_EXCL))
		result = -EEXIST;
	for (open_index = 0; result == 0 && open_index < OPEN_COUNT && opens[open_index].used; open_index++)
		;
	if (result == 0 && open_index == OPEN_COUNT)
		result = -EMFILE;
	if (result == 0)
	{
		if (!slot->exists)
			clock_gettime(CLOCK_REALTIME, &slot->modified);
		slot->exists = 1;
		if (flags & O_TRUNC)
			resize(slot, 0);
		opens[open_index].used = 1;
		opens[open_index].slot = index;
		opens[open_index].position = 0;
		result = HOST_MEMORY_FILE_DESCRIPTOR + open_index;
	}
	pthread_mutex_unlock(&lock);
	return result;
}

int host_memory_file_close(int descriptor)
{
	struct open_file *file;

	pthread_mutex_lock(&lock);
	file = open_of(descriptor);
	if (file)
		file->used = 0;
	pthread_mutex_unlock(&lock);
	return file ? 0 : -EBADF;
}

/* (with the lock held) */
static long long read_at(struct slot *slot, void *buffer, size_t count, unsigned long long offset)
{
	size_t total = 0;

	while (total < count && offset + total < slot->size)
	{
		unsigned long long at = offset + total;
		unsigned long piece = (unsigned long)(at / PIECE_SIZE);
		unsigned long within = (unsigned long)(at % PIECE_SIZE);
		size_t wanted = count - total;

		if (wanted > PIECE_SIZE - within)
			wanted = PIECE_SIZE - within;
		if (wanted > slot->size - at)
			wanted = (size_t)(slot->size - at);
		if (piece < slot->piece_count && slot->pieces[piece])
			memcpy((char *)buffer + total, slot->pieces[piece] + within, wanted);
		else
			memset((char *)buffer + total, 0, wanted);
		total += wanted;
	}
	return (long long)total;
}

/* (with the lock held) */
static long long write_at(struct slot *slot, const void *buffer, size_t count, unsigned long long offset)
{
	static int told;
	size_t total = 0;

	if (offset + count > slot->size && resize(slot, offset + count) != 0)
		return -ENOMEM;
	while (total < count)
	{
		unsigned long long at = offset + total;
		unsigned long piece = (unsigned long)(at / PIECE_SIZE);
		unsigned long within = (unsigned long)(at % PIECE_SIZE);
		size_t wanted = count - total;

		if (wanted > PIECE_SIZE - within)
			wanted = PIECE_SIZE - within;
		if (!slot->pieces[piece])
		{
			slot->pieces[piece] = calloc(1, PIECE_SIZE);
			if (!slot->pieces[piece])
			{
				if (!told)
				{
					told = 1;
					/* (logged without the lock the logger may want: the
					card's lock is not held here) */
					host_logf(HOST_LOG_ERROR, "map cache: no memory for more of a map (%lu MB held)",
						megabytes_held());
				}
				return total ? (long long)total : -ENOSPC;
			}
			pieces_held++;
		}
		memcpy(slot->pieces[piece] + within, (const char *)buffer + total, wanted);
		total += wanted;
	}
	return (long long)total;
}

long long host_memory_file_pread(int descriptor, void *buffer, size_t count, long long offset)
{
	struct open_file *file;
	long long result = -EBADF;

	if (offset < 0)
		return -EINVAL;
	pthread_mutex_lock(&lock);
	file = open_of(descriptor);
	if (file)
		result = read_at(&slots[file->slot], buffer, count, (unsigned long long)offset);
	pthread_mutex_unlock(&lock);
	return result;
}

long long host_memory_file_pwrite(int descriptor, const void *buffer, size_t count, long long offset)
{
	struct open_file *file;
	long long result = -EBADF;

	if (offset < 0)
		return -EINVAL;
	pthread_mutex_lock(&lock);
	file = open_of(descriptor);
	if (file)
		result = write_at(&slots[file->slot], buffer, count, (unsigned long long)offset);
	pthread_mutex_unlock(&lock);
	return result;
}

long long host_memory_file_read(int descriptor, void *buffer, size_t count)
{
	struct open_file *file;
	long long result = -EBADF;

	pthread_mutex_lock(&lock);
	file = open_of(descriptor);
	if (file)
	{
		result = read_at(&slots[file->slot], buffer, count, file->position);
		if (result > 0)
			file->position += (unsigned long long)result;
	}
	pthread_mutex_unlock(&lock);
	return result;
}

long long host_memory_file_write(int descriptor, const void *buffer, size_t count)
{
	struct open_file *file;
	long long result = -EBADF;

	pthread_mutex_lock(&lock);
	file = open_of(descriptor);
	if (file)
	{
		result = write_at(&slots[file->slot], buffer, count, file->position);
		if (result > 0)
			file->position += (unsigned long long)result;
	}
	pthread_mutex_unlock(&lock);
	return result;
}

long long host_memory_file_seek(int descriptor, long long offset, int whence)
{
	struct open_file *file;
	long long result = -EBADF;

	pthread_mutex_lock(&lock);
	file = open_of(descriptor);
	if (file)
	{
		long long base = whence == SEEK_SET ? 0 : whence == SEEK_CUR ? (long long)file->position :
			whence == SEEK_END ? (long long)slots[file->slot].size : -1;

		if (base < 0 || base + offset < 0)
			result = -EINVAL;
		else
		{
			file->position = (unsigned long long)(base + offset);
			result = (long long)file->position;
		}
	}
	pthread_mutex_unlock(&lock);
	return result;
}

int host_memory_file_truncate(int descriptor, long long size)
{
	struct open_file *file;
	int result = -EBADF;
	int index = -1;
	unsigned long given_back = 0;
	unsigned long held = 0;

	if (size < 0)
		return -EINVAL;
	pthread_mutex_lock(&lock);
	file = open_of(descriptor);
	if (file)
	{
		unsigned long before = pieces_held;

		index = file->slot;
		result = resize(&slots[index], (unsigned long long)size);
		given_back = before - pieces_held;
		held = megabytes_held();
	}
	pthread_mutex_unlock(&lock);
	if (given_back)
		host_logf(HOST_LOG_INFO, "map cache: slot %d gave back %lu MB for its next map; %lu MB held in all",
			index, given_back * (PIECE_SIZE / (1024 * 1024)), held);
	return result;
}

/* (with the lock held) a slot's description as stat gives a file's */
static void describe(const struct slot *slot, struct stat *out)
{
	memset(out, 0, sizeof(*out));
	out->st_mode = S_IFREG | 0644;
	out->st_nlink = 1;
	out->st_size = (off_t)slot->size;
	out->st_blksize = 512;
	out->st_blocks = (blkcnt_t)((slot->size + 511) / 512);
	out->st_atim = slot->modified;
	out->st_mtim = slot->modified;
	out->st_ctim = slot->modified;
}

int host_memory_file_fstat(int descriptor, struct stat *out)
{
	struct open_file *file;
	int result = -EBADF;

	pthread_mutex_lock(&lock);
	file = open_of(descriptor);
	if (file)
	{
		describe(&slots[file->slot], out);
		result = 0;
	}
	pthread_mutex_unlock(&lock);
	return result;
}

int host_memory_file_stat(int index, const char *path, struct stat *out)
{
	int result = -ENOENT;

	pthread_mutex_lock(&lock);
	forget_card_file(index, path);
	if (slots[index].exists)
	{
		describe(&slots[index], out);
		result = 0;
	}
	pthread_mutex_unlock(&lock);
	return result;
}

int host_memory_file_unlink(int index, const char *path)
{
	struct slot *slot = &slots[index];
	int result = -ENOENT;

	pthread_mutex_lock(&lock);
	forget_card_file(index, path);
	if (slot->exists)
	{
		free_pieces(slot, 0);
		free(slot->pieces);
		memset(slot, 0, sizeof(*slot));
		slot->card_file_checked = 1;
		result = 0;
	}
	pthread_mutex_unlock(&lock);
	return result;
}

/* times as utimensat takes them: [0] access, [1] modification; NULL now */
int host_memory_file_set_times(int index, const struct timespec *times)
{
	struct slot *slot = &slots[index];
	int result = -ENOENT;

	pthread_mutex_lock(&lock);
	if (slot->exists)
	{
		if (!times || times[1].tv_nsec == UTIME_NOW)
			clock_gettime(CLOCK_REALTIME, &slot->modified);
		else if (times[1].tv_nsec != UTIME_OMIT)
			slot->modified = times[1];
		result = 0;
	}
	pthread_mutex_unlock(&lock);
	return result;
}
