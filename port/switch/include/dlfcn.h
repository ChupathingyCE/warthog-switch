/*
DLFCN.H

Symbol lookup, for the Switch port.

The shared layer's posix_files.c, which the host compiles, names a code
address for crash backtraces with dladdr. A homebrew program is one static
image with no dynamic linker, so there is nothing to ask: dladdr finds no
symbol, and posix_describe_address prints the bare address, which
aarch64-none-elf-addr2line -e build/switch/halo.elf (or llvm-symbolizer with
the guest image, for a guest address) turns into a name.
*/

#ifndef __HALO_SWITCH_DLFCN_H
#define __HALO_SWITCH_DLFCN_H

typedef struct
{
	const char *dli_fname;
	void *dli_fbase;
	const char *dli_sname;
	void *dli_saddr;
} Dl_info;

static inline int dladdr(const void *address, Dl_info *information)
{
	(void)address;
	information->dli_fname = 0;
	information->dli_fbase = 0;
	information->dli_sname = 0;
	information->dli_saddr = 0;
	return 0;
}

#endif
