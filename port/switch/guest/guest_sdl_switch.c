/*
GUEST_SDL_SWITCH.C

The SDL3 functions the game's platform layer calls (sdl_platform.c,
xinput_sdl.c, menu_files.c, browser.c, updater.c, vrr.c) that the Android
guest runtime's guest_sdl.c does not answer, for the Switch's guest: what a
console with one window, no properties, no log hook and no shared libraries
answers, and the files and folders through the platform layer's posix
helpers (posix.h), which the host answers.
*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <SDL3/SDL.h>

#include "posix.h"

/* (port/switch/host/host_sdl2.c) */
unsigned int host_sdl_gamepad_id(unsigned int gamepad);
unsigned int host_sdl_gamepad_vendor(unsigned int gamepad);
unsigned int host_sdl_gamepad_product(unsigned int gamepad);
int host_power_percent(void);
int host_power_state(void);
int host_sdl_key_from_scancode(int scancode);

/* the battery, as the host's power service says it (SDL3's states: on
battery, charging, charged) */
SDL_PowerState SDL_GetPowerInfo(int *seconds, int *percent)
{
	if (seconds)
		*seconds = -1;
	if (percent)
		*percent = host_power_percent();
	return (SDL_PowerState)host_power_state();
}

/* a key's keycode by its scancode (the modifiers left as SDL3 leaves them
for a key event's own keycode) */
SDL_Keycode SDL_GetKeyFromScancode(SDL_Scancode scancode, SDL_Keymod modstate, bool key_event)
{
	(void)modstate;
	(void)key_event;
	return (SDL_Keycode)host_sdl_key_from_scancode((int)scancode);
}

const char *SDL_getenv(const char *name)
{
	return getenv(name);
}

SDL_JoystickID SDL_GetGamepadID(SDL_Gamepad *gamepad)
{
	return (SDL_JoystickID)host_sdl_gamepad_id((unsigned int)(uintptr_t)gamepad);
}

Uint16 SDL_GetGamepadVendor(SDL_Gamepad *gamepad)
{
	return (Uint16)host_sdl_gamepad_vendor((unsigned int)(uintptr_t)gamepad);
}

Uint16 SDL_GetGamepadProduct(SDL_Gamepad *gamepad)
{
	return (Uint16)host_sdl_gamepad_product((unsigned int)(uintptr_t)gamepad);
}

/* (the game's log is its own; SDL's messages are the host's) */
void SDL_SetLogOutputFunction(SDL_LogOutputFunction callback, void *userdata)
{
	(void)callback;
	(void)userdata;
}

void SDL_SetLogPriority(int category, SDL_LogPriority priority)
{
	(void)category;
	(void)priority;
}

/* (no window properties: every property its default, HDR off) */
SDL_PropertiesID SDL_GetWindowProperties(SDL_Window *window)
{
	(void)window;
	return 0;
}

bool SDL_GetBooleanProperty(SDL_PropertiesID props, const char *name, bool default_value)
{
	(void)props;
	(void)name;
	return default_value;
}

float SDL_GetFloatProperty(SDL_PropertiesID props, const char *name, float default_value)
{
	(void)props;
	(void)name;
	return default_value;
}

int SDL_GetVersion(void)
{
	return SDL_VERSION;
}

const char *SDL_GetCurrentVideoDriver(void)
{
	return "switch";
}

/* (the window and its context last the process: the deko3d renderer's) */
bool SDL_GL_DestroyContext(SDL_GLContext context)
{
	(void)context;
	return true;
}

void SDL_DestroyWindow(SDL_Window *window)
{
	(void)window;
}

/* ---------- files */

bool SDL_GetPathInfo(const char *path, SDL_PathInfo *info)
{
	struct posix_file_information status;
	int directory;

	if (!path || posix_stat(path, &status))
		return false;
	if (info)
	{
		directory = (status.flags & _posix_file_is_directory) != 0;
		memset(info, 0, sizeof(*info));
		info->type = directory ? SDL_PATHTYPE_DIRECTORY : SDL_PATHTYPE_FILE;
		info->size = directory ? 0 : ((Uint64)status.size_high << 32) | status.size_low;
		info->create_time = (SDL_Time)status.creation_seconds * 1000000000LL + status.creation_nanoseconds;
		info->modify_time = (SDL_Time)status.modification_seconds * 1000000000LL + status.modification_nanoseconds;
		info->access_time = (SDL_Time)status.access_seconds * 1000000000LL + status.access_nanoseconds;
	}
	return true;
}

static int glob_lower(int c, int folded)
{
	return folded && c >= 'A' && c <= 'Z' ? c - 'A' + 'a' : c;
}

/* SDL's glob within one part of a path: * any run of characters, ? one;
neither crosses a / (the caller matches a part at a time) */
static int glob_part(const char *pattern, const char *name, int folded)
{
	if (!*pattern)
		return !*name;
	if (*pattern == '*')
	{
		for (;; name++)
		{
			if (glob_part(pattern + 1, name, folded))
				return 1;
			if (!*name)
				return 0;
		}
	}
	if (!*name)
		return 0;
	if (*pattern != '?' && glob_lower((unsigned char)*pattern, folded) != glob_lower((unsigned char)*name, folded))
		return 0;
	return glob_part(pattern + 1, name + 1, folded);
}

struct glob_found
{
	char **names;
	int count;
	int capacity;
};

/* the entries below folder (relative as prefix) matching the pattern's
parts from part on */
static void glob_walk(const char *folder, const char *prefix, char **parts, int part, int part_count, int folded,
	struct glob_found *found)
{
	void *entries = posix_directory_open(folder);
	char name[256];

	if (!entries)
		return;
	while (posix_directory_next(entries, name, sizeof(name)))
	{
		char *relative, *path;
		size_t prefix_length = strlen(prefix), name_length = strlen(name);

		if (!glob_part(parts[part], name, folded))
			continue;
		relative = malloc(prefix_length + name_length + 2);
		path = malloc(strlen(folder) + name_length + 2);
		if (!relative || !path)
		{
			free(relative);
			free(path);
			continue;
		}
		strcpy(relative, prefix);
		if (prefix_length)
			strcat(relative, "/");
		strcat(relative, name);
		strcpy(path, folder);
		if (path[0] && path[strlen(path) - 1] != '/')
			strcat(path, "/");
		strcat(path, name);
		if (part + 1 < part_count)
		{
			struct posix_file_information status;

			if (!posix_stat(path, &status) && (status.flags & _posix_file_is_directory))
				glob_walk(path, relative, parts, part + 1, part_count, folded, found);
			free(relative);
		}
		else
		{
			if (found->count == found->capacity)
			{
				int capacity = found->capacity ? found->capacity * 2 : 16;
				char **grown = realloc(found->names, (size_t)capacity * sizeof(*grown));

				if (!grown)
				{
					free(relative);
					free(path);
					continue;
				}
				found->names = grown;
				found->capacity = capacity;
			}
			found->names[found->count++] = relative;
		}
		free(path);
	}
	posix_directory_close(entries);
}

/* as SDL's: the names below path (relative to it) that pattern matches (all
of them with no pattern), in one allocation SDL_free frees: the pointers,
a NULL, then the strings */
char **SDL_GlobDirectory(const char *path, const char *pattern, SDL_GlobFlags flags, int *count)
{
	struct glob_found found = { NULL, 0, 0 };
	char *copy, *parts[16], *cursor, **result = NULL;
	int part_count = 0, index;
	size_t strings = 0;

	if (count)
		*count = 0;
	if (!path)
		return NULL;
	copy = strdup(pattern && *pattern ? pattern : "*");
	if (!copy)
		return NULL;
	for (cursor = strtok(copy, "/"); cursor && part_count < 16; cursor = strtok(NULL, "/"))
		parts[part_count++] = cursor;
	if (part_count)
		glob_walk(path, "", parts, 0, part_count, (flags & SDL_GLOB_CASEINSENSITIVE) != 0, &found);
	free(copy);
	for (index = 0; index < found.count; index++)
		strings += strlen(found.names[index]) + 1;
	result = malloc((size_t)(found.count + 1) * sizeof(char *) + strings);
	if (result)
	{
		char *text = (char *)(result + found.count + 1);

		for (index = 0; index < found.count; index++)
		{
			size_t length = strlen(found.names[index]) + 1;

			memcpy(text, found.names[index], length);
			result[index] = text;
			text += length;
		}
		result[found.count] = NULL;
		if (count)
			*count = found.count;
	}
	for (index = 0; index < found.count; index++)
		free(found.names[index]);
	free(found.names);
	return result;
}

/* ---------- no shared libraries (vrr.c's X11, on the desktop) */

void *dlopen(const char *file, int mode)
{
	(void)file;
	(void)mode;
	return NULL;
}

void *dlsym(void *handle, const char *name)
{
	(void)handle;
	(void)name;
	return NULL;
}

/* ---------- voice chat (port/linux/src/voice.c): the headset's microphone,
the host's libnx audin (port/switch/host/host_microphone.c), opened as the
guest runtime's SDL_OpenAudioDeviceStream opens any stream */

int host_sdl_get_audio_stream_data(unsigned int stream, void *data, int length);
int host_sdl_get_audio_stream_available(unsigned int stream);
void host_sdl_clear_audio_stream(unsigned int stream);

/* (the host starts its SDL whole before the guest runs, and the microphone
needs no subsystem of SDL's) */
SDL_InitFlags SDL_WasInit(SDL_InitFlags flags)
{
	return flags;
}

bool SDL_InitSubSystem(SDL_InitFlags flags)
{
	(void)flags;
	return true;
}

/* (one microphone, the system's: none to choose by name) */
SDL_AudioDeviceID *SDL_GetAudioRecordingDevices(int *count)
{
	if (count)
		*count = 0;
	return NULL;
}

int SDL_GetAudioStreamData(SDL_AudioStream *stream, void *data, int length)
{
	return host_sdl_get_audio_stream_data((unsigned int)(uintptr_t)stream, data, length);
}

int SDL_GetAudioStreamAvailable(SDL_AudioStream *stream)
{
	return host_sdl_get_audio_stream_available((unsigned int)(uintptr_t)stream);
}

bool SDL_ClearAudioStream(SDL_AudioStream *stream)
{
	host_sdl_clear_audio_stream((unsigned int)(uintptr_t)stream);
	return true;
}

/* (the microphone keeps recording; voice chat clears it when it resumes) */
bool SDL_PauseAudioStreamDevice(SDL_AudioStream *stream)
{
	(void)stream;
	return true;
}

/* (voice chat's timing: the monotonic clock, in nanoseconds) */
Uint64 SDL_GetPerformanceCounter(void)
{
	struct timespec now;

	clock_gettime(CLOCK_MONOTONIC, &now);
	return (Uint64)now.tv_sec * 1000000000u + (Uint64)now.tv_nsec;
}

Uint64 SDL_GetPerformanceFrequency(void)
{
	return 1000000000u;
}

/* (clips' frame times, capture_clips.c: nanoseconds since the first ask,
as SDL counts them from its start) */
Uint64 SDL_GetTicksNS(void)
{
	static Uint64 start;
	Uint64 now = SDL_GetPerformanceCounter();

	if (!start)
		start = now;
	return now - start;
}

/* (a file whole, as SDL reads it: voice chat's test feed, a WAV) */
void *SDL_LoadFile(const char *file, size_t *datasize)
{
	FILE *stream = fopen(file, "rb");
	unsigned char *data = NULL;
	size_t size = 0, room = 0, got;

	if (datasize)
		*datasize = 0;
	if (!stream)
		return NULL;
	for (;;)
	{
		if (size + 1 >= room)
		{
			unsigned char *more = realloc(data, room ? room * 2 : 65536);

			if (!more)
			{
				free(data);
				fclose(stream);
				return NULL;
			}
			data = more;
			room = room ? room * 2 : 65536;
		}
		got = fread(data + size, 1, room - size - 1, stream);
		if (!got)
			break;
		size += got;
	}
	fclose(stream);
	data[size] = 0;
	if (datasize)
		*datasize = size;
	return data;
}
