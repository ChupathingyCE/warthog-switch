/*
HOST_TOUCH.C

What Warthog's guest imports from the Android host that the Switch host
does not answer elsewhere (host_sdl2.c has the touch screen, the message
boxes, the gesture edges and the rumble): there is no web browser to open a
link in.
*/

#include "host.h"

#include <stdint.h>
#include <string.h>

int host_sdl_open_url(const char *url)
{
	host_logf(HOST_LOG_INFO, "cannot open %s: no web browser here", url ? url : "");
	return 0;
}
