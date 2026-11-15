/*
HOST_MCC_PREVIEW.C

posix_mcc_preview_read for the Switch: the game's (port/linux/src/
posix_mcc_preview.c) walks a package's folders through held descriptors
(openat, fdopendir), which the Switch's C library does not have. This one
walks the same way by path, under the package root the game chose: each
part of the relative path is checked as the game checks it, matched without
regard to case against its folder's entries (an ambiguous match is refused,
as there), and only a regular file of at most the buffer's size is read,
whole. The SD card's FAT has no links to follow.
*/

#include "host.h"

#include <ctype.h>
#include <dirent.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>
#include <unistd.h>

#define MCC_PREVIEW_PATH_MAXIMUM 1024

static int component(const char *part)
{
	const unsigned char *p = (const unsigned char *)part;
	size_t n = strlen(part);

	if (!n || n > 127 || part[n - 1] == '.' || part[n - 1] == ' ')
		return 0;
	if (!strcmp(part, ".") || !strcmp(part, ".."))
		return 0;
	for (; *p; p++)
		if (*p < 32 || *p == 127 || strchr(":*?\"<>|/\\", *p))
			return 0;
	return 1;
}

/* the entry of folder path matching part, appended to path; 0 when none or
more than one does */
static int append_match(char *path, size_t *used, const char *part)
{
	DIR *entries = opendir(path);
	struct dirent *entry;
	char found[256];
	int matches = 0;
	size_t n;

	if (!entries)
		return 0;
	while ((entry = readdir(entries)) != NULL)
		if (!strcasecmp(part, entry->d_name) && strlen(entry->d_name) < sizeof(found))
		{
			strcpy(found, entry->d_name);
			matches++;
		}
	closedir(entries);
	n = strlen(found);
	if (matches != 1 || *used + 1 + n + 1 > MCC_PREVIEW_PATH_MAXIMUM)
		return 0;
	path[(*used)++] = '/';
	memcpy(path + *used, found, n + 1);
	*used += n;
	return 1;
}

int posix_mcc_preview_read(const char *root, const char *relative, void *buffer, unsigned int capacity)
{
	char path[MCC_PREVIEW_PATH_MAXIMUM], part[128];
	const char *cursor = relative;
	struct stat status;
	size_t used, done = 0;
	int descriptor, result = 0;

	if (!root || !relative || !*relative || !buffer || !capacity || capacity > 8 * 1024 * 1024)
		return 0;
	used = strlen(root);
	if (!used || used >= sizeof(path))
		return 0;
	memcpy(path, root, used + 1);
	while (used > 1 && path[used - 1] == '/')
		path[--used] = '\0';
	if (stat(path, &status) || !S_ISDIR(status.st_mode))
		return 0;
	while (*cursor)
	{
		size_t n = strcspn(cursor, "/\\");
		if (!n || n >= sizeof(part))
			return 0;
		memcpy(part, cursor, n);
		part[n] = '\0';
		if (!component(part))
			return 0;
		cursor += n;
		if (*cursor && !*++cursor)
			return 0;
		if (!append_match(path, &used, part))
			return 0;
		if (stat(path, &status) || (*cursor ? !S_ISDIR(status.st_mode) : !S_ISREG(status.st_mode)))
			return 0;
	}
	if (status.st_size <= 0 || (unsigned long long)status.st_size > capacity)
		return 0;
	descriptor = open(path, O_RDONLY);
	if (descriptor < 0)
		return 0;
	while (done < (size_t)status.st_size)
	{
		ssize_t got = read(descriptor, (char *)buffer + done, (size_t)status.st_size - done);
		if (got <= 0)
			break;
		done += (size_t)got;
	}
	if (done == (size_t)status.st_size)
	{
		char extra;
		if (read(descriptor, &extra, 1) == 0)
			result = (int)done;
	}
	close(descriptor);
	return result;
}
