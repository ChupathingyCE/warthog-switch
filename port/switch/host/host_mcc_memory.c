/*
HOST_MCC_MEMORY.C

The window MCC maps' linked tags are loaded at (port/linux/src/mcc_memory.c,
which hands it to the host on Android-built guests): 64 MB at the address the
map was linked for, 0x50000000 for MCC's Tool. The Android host's version
(port/android/host/host_mcc_memory.c) holds the window from start-up so that
the process's later allocations stay out of it; here everything below 4 GB is
the guest's own and nothing else maps there by chance (host_mman.c), so the
window is mapped when a map asks for it and given back when it is done; its
usual address, 0x50000000, is kept free of the Xbox window and the pools from
the start (host_memory.c, MCC_TAG_BASE), and a map linked elsewhere is mapped
only where nothing of the port's is. The
rules on the address and the size are the Android host's.
*/

#include "host.h"

#include <errno.h>
#include <pthread.h>
#include <stdint.h>
#include <sys/mman.h>

#define MCC_TAG_SIZE 0x04000000u

static pthread_mutex_t mcc_lock = PTHREAD_MUTEX_INITIALIZER;
static void *mcc_window;

long long host_mcc_memory_reserve(unsigned int address, unsigned int size)
{
	void *wanted = (void *)(uintptr_t)address;
	void *result;
	int error = 0;

	if ((address & 0xffffu) || size != MCC_TAG_SIZE || address < 0x42000000u || address > 0x70000000u)
		return -EINVAL;
	pthread_mutex_lock(&mcc_lock);
	if (mcc_window)
		error = -EBUSY;
	else if (!host_memory_mcc_range_free(address, MCC_TAG_SIZE))
	{
		error = -EEXIST;
		host_logf(HOST_LOG_WARN, "mcc memory: %08x-%08x is the port's (the window, a pool or the image); the map "
			"cannot load", address, address + MCC_TAG_SIZE);
	}
	else
	{
		result = mmap(wanted, MCC_TAG_SIZE, PROT_READ | PROT_WRITE,
			MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
		if (result == wanted)
			mcc_window = result;
		else
		{
			error = result == MAP_FAILED ? -errno : -EEXIST;
			if (result != MAP_FAILED)
				munmap(result, MCC_TAG_SIZE);
			host_logf(HOST_LOG_WARN, "mcc memory: cannot map %08x-%08x (%d)", address, address + MCC_TAG_SIZE,
				-error);
		}
	}
	pthread_mutex_unlock(&mcc_lock);
	return error ? (long long)error : (long long)address;
}

int host_mcc_memory_release(unsigned int address, unsigned int size)
{
	int error = 0;

	pthread_mutex_lock(&mcc_lock);
	if (!mcc_window || mcc_window != (void *)(uintptr_t)address || size != MCC_TAG_SIZE)
		error = -EINVAL;
	else if (munmap(mcc_window, MCC_TAG_SIZE))
		error = -errno;
	else
		mcc_window = NULL;
	pthread_mutex_unlock(&mcc_lock);
	return error;
}
