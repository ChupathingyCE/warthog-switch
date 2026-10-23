/*
HOST_TLS.C

What the game's Mbed TLS (port/third_party/mbedtls, built into this host for
the game list's requests: port/linux/src/posix_browser.c) needs of the
console: its entropy and a millisecond clock. The library's own platform
sources draw on /dev/urandom or getrandom and on a POSIX version the C
library does not claim, which libnx has not; built with
MBEDTLS_NO_PLATFORM_ENTROPY, MBEDTLS_ENTROPY_HARDWARE_ALT and
MBEDTLS_PLATFORM_MS_TIME_ALT (port/switch/build.py) it asks here instead:
the console's random service answers (randomGet: the kernel's, seeded by
hardware), and its monotonic clock.
*/

#include <switch.h>
#include <stddef.h>
#include <time.h>

#include "mbedtls/entropy.h"
#include "mbedtls/platform_time.h"

mbedtls_ms_time_t mbedtls_ms_time(void)
{
	struct timespec now;

	if (clock_gettime(CLOCK_MONOTONIC, &now) != 0)
		return (mbedtls_ms_time_t)time(NULL) * 1000;
	return (mbedtls_ms_time_t)now.tv_sec * 1000 + now.tv_nsec / 1000000;
}

int mbedtls_hardware_poll(void *data, unsigned char *output, size_t length, size_t *olen)
{
	(void)data;
	randomGet(output, length);
	*olen = length;
	return 0;
}
