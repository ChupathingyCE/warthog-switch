/*
HOST_BROWSER.C

The game list's requests (port/linux/src/browser_http.h), which Warthog's
guest imports and the Android host answers with posix_browser.c and mbedtls.
The Switch host has no game list yet: every
request fails with a reason, and there is no player key, so the guest's
browser reports that it cannot reach the list and the rest of the game is
untouched.
*/

#include "host.h"

#include <pthread.h>
#include <stdio.h>
#include <stddef.h>

int posix_browser_request(const char *url, const char *body, const char *content_type, char *response,
	int response_size, char *error, int error_size)
{
	(void)url;
	(void)body;
	(void)content_type;
	if (response && response_size > 0)
		response[0] = 0;
	if (error && error_size > 0)
		snprintf(error, (size_t)error_size, "the game list is not on the Switch yet");
	return 0;
}

int posix_browser_request_as(const char *url, const char *body, const char *content_type, const char *user_agent,
	char *response, int response_size, char *error, int error_size)
{
	(void)user_agent;
	return posix_browser_request(url, body, content_type, response, response_size, error, error_size);
}

int posix_browser_send(const char *url, const char *body, size_t body_length, const char *content_type,
	const char *headers, char *response, int response_size, char *error, int error_size)
{
	(void)body_length;
	(void)headers;
	return posix_browser_request(url, body, content_type, response, response_size, error, error_size);
}

int posix_browser_private_key(const char *path, unsigned char *key, int size)
{
	(void)path;
	(void)key;
	(void)size;
	return 0;
}

int posix_browser_replace_key(const char *path, const unsigned char *key, int size)
{
	(void)path;
	(void)key;
	(void)size;
	return 0;
}


/* a download of a file (the map sharing's and the updater's downloads over
the game list's connection), which fails as the requests above do */
int posix_browser_download_open(const char *url, const char *user_agent, int *status, int *length, char *error,
	int error_size)
{
	(void)url;
	(void)user_agent;
	if (status)
		*status = 0;
	if (length)
		*length = -1;
	if (error && error_size > 0)
		snprintf(error, (size_t)error_size, "the game list is not on the Switch yet");
	return 0;
}

int posix_browser_download_read(int download, void *buffer, int size)
{
	(void)download;
	(void)buffer;
	(void)size;
	return -1;
}

void posix_browser_download_close(int download)
{
	(void)download;
}

/* the lock the game list's callers take around their requests: kept, so
that the callers' order holds when there is a game list to talk to */
static pthread_mutex_t browser_lock = PTHREAD_MUTEX_INITIALIZER;

void posix_browser_lock(void)
{
	pthread_mutex_lock(&browser_lock);
}

void posix_browser_unlock(void)
{
	pthread_mutex_unlock(&browser_lock);
}
