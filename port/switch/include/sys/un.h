/*
SYS_UN_H

<sys/un.h> for the Switch port, which newlib and libnx have not.

miniupnpc (port/third_party/miniupnpc, minissdpc.c) asks a local minissdpd
daemon over a Unix socket for the routers it has seen before searching the
network itself. The console has no Unix sockets - socket(AF_UNIX, ...)
fails - so the address is declared only for the library to compile, and
the search on the network (SSDP) is what finds the router.
*/

#ifndef SWITCH_SYS_UN_H
#define SWITCH_SYS_UN_H

#include <sys/socket.h>

struct sockaddr_un
{
	unsigned char sun_len;
	sa_family_t sun_family;
	char sun_path[104];
};

#endif
