/*
HOST_UPNP_NAMES.H

Included ahead of miniupnpc's sources on the Switch (port/switch/build.py):
the two interface calls libnx has not, under the names the build gives
them (host_net.c's).
*/

#ifndef HOST_UPNP_NAMES_H
#define HOST_UPNP_NAMES_H

unsigned int switch_upnp_if_nametoindex(const char *name);
char *switch_upnp_if_indextoname(unsigned int index, char *name);

#endif
