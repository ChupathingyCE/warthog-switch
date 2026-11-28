/*
GAME_CONSOLE_GAPS.C

Game functions the Switch's build calls but the game builds to nothing on a
console. The game takes it that no console has the game list
(HALO_GAME_BROWSER: halo_console_features.h, "which no console build has"),
and the Switch does: so units built for the game list (profile_names.c,
lobby_screen.c, server_commands.c, network_server_manager.c, probe.c,
networks.c) call what a console leaves out (Delta's device identity, the
Guide's party and friends, Steam, MCC maps); and forge.c, built on a
console with Forge's hooks away, calls its AI tags and the vehicles' homes. Each answers here as the game would with that
part away, and only while that part is away (the Guide's and MCC's are
the Switch's now). They go when upstream gates its callers as it gates
these.
*/

#include <stdio.h>
#include <string.h>

/* ---------- Delta's device identity (port/linux/src/identity.c, out under
HALO_CONSOLE_NO_DELTA_IDENTITY) */

#define IDENTITY_ID_SIZE 16

/* (no verified players: no name passes for one's handle) */
int identity_impersonates(const char *name, const char *handle, int cut)
{
	(void)name;
	(void)handle;
	(void)cut;
	return 0;
}

/* (no verified mark to tell names apart by: the name as it is, which the
caller then shows as it is) */
int identity_unverified_name(const unsigned short *name, int length, unsigned short *out, int size)
{
	int index;

	for (index = 0; index < length && index < size && name[index]; index++)
		out[index] = name[index];
	return index;
}

static int hex_digit(char c)
{
	return c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : c >= 'A' && c <= 'F' ? c - 'A' + 10 :
		-1;
}

/* a profile's account file's line, read as the game reads it: 0 a guest
("guest"), 2 that account (32 hex digits, into account), 1 the copy's own
account for the owner, a guest for any other */
int identity_account_choice(const char *line, int owner, unsigned char *account)
{
	char text[80];
	const char *at = line ? line : "";
	int length, index;

	if ((unsigned char)at[0] == 0xEF && (unsigned char)at[1] == 0xBB && (unsigned char)at[2] == 0xBF)
		at += 3;
	while (*at == ' ' || *at == '\t')
		at++;
	snprintf(text, sizeof(text), "%s", at);
	length = (int)strlen(text);
	while (length && (text[length - 1] == ' ' || text[length - 1] == '\t' || text[length - 1] == '\r' ||
		text[length - 1] == '\n'))
	{
		length--;
	}
	text[length] = 0;
	if (!strcmp(text, "guest"))
		return 0;
	if (length == 2 * IDENTITY_ID_SIZE)
	{
		for (index = 0; index < IDENTITY_ID_SIZE; index++)
		{
			int high = hex_digit(text[2 * index]), low = hex_digit(text[2 * index + 1]);

			if (high < 0 || low < 0)
				break;
			account[index] = (unsigned char)(high << 4 | low);
		}
		if (index == IDENTITY_ID_SIZE)
			return 2;
	}
	return owner ? 1 : 0;
}

/* the networks' certificates (networks.c, built for the game list, checks a
network list's issuers with these): none is ever trusted, as a console has
no Delta identity to check them against. Every issuer is malformed and every
key weak, so networks.c refuses each list it is handed */

struct identity_issuer;

int identity_parse_issuer(const unsigned char *data, int size, struct identity_issuer *issuer)
{
	(void)data;
	(void)size;
	(void)issuer;
	return 0;
}

int identity_check_issuer(const unsigned char *data, int size, const unsigned char (*roots)[32], int root_count,
	unsigned long now, struct identity_issuer *issuer)
{
	(void)data;
	(void)size;
	(void)roots;
	(void)root_count;
	(void)now;
	(void)issuer;
	return 1; /* IDENTITY_MALFORMED */
}

int identity_issuer_signed_by(const unsigned char *data, int size, const unsigned char *root)
{
	(void)data;
	(void)size;
	(void)root;
	return 0;
}

int identity_key_weak(const unsigned char *public_key)
{
	(void)public_key;
	return 1;
}

/* ---------- Forge's AI tags and the vehicles' homes (forge_ai_tags.c and
game_engine.c's, out under HALO_CONSOLE_NO_FORGE; forge.c is built on a
console with Forge's hooks away, and calls them). No character is ever
brought in, and no vehicle has a home Forge took */

#ifdef HALO_CONSOLE_NO_FORGE

unsigned char forge_ai_tags_update(void)
{
	return 0;
}

unsigned char forge_ai_tags_pending(void)
{
	return 0;
}

char const *forge_ai_tags_source_map(long tag_index)
{
	(void)tag_index;
	return NULL;
}

short forge_ai_tags_faction_count(void)
{
	return 0;
}

unsigned char forge_ai_tags_faction(short faction, char const **name, char const **map)
{
	(void)faction;
	if (name)
		*name = NULL;
	if (map)
		*map = NULL;
	return 0;
}

short forge_ai_tags_faction_category(short faction)
{
	(void)faction;
	return -1; /* NONE */
}

/* (what forge_ai_tags.c says with no characters brought in: every tag is
the map's own, and the map's are offered) */
unsigned char forge_ai_tags_offered(long tag_index)
{
	(void)tag_index;
	return 1;
}

short forge_ai_tags_faction_of(long tag_index)
{
	(void)tag_index;
	return -1; /* NONE */
}

void game_engine_vehicle_home_forget(long object_index)
{
	(void)object_index;
}
#endif

/* ---------- the Guide's party and friends (port/linux/src/browser.c, out
under HALO_CONSOLE_NO_GUIDE: the Switch has the Guide, HALO_CONSOLE_GUIDE,
so these answer only a build that turns it off) */

#ifdef HALO_CONSOLE_NO_GUIDE

struct social_party;
struct social_state;

/* (never a party: the serial never moves, so the caller's stays as it was) */
void browser_party_get(struct social_party *party, int *serial)
{
	(void)party;
	(void)serial;
}

int browser_social_get(struct social_state *state, int *serial)
{
	(void)state;
	(void)serial;
	return 0; /* BROWSER_SOCIAL_NONE */
}
#endif

#if !HALO_MCC

/* ---------- Steam (port/linux/src/steam_bridge_pipe.c, out with HALO_MCC 0) */

int steam_link_progress(const char *id_text, unsigned long long *done, unsigned long long *total, char *error,
	int error_size)
{
	(void)id_text;
	if (done)
		*done = 0;
	if (total)
		*total = 0;
	if (error && error_size > 0)
		snprintf(error, (size_t)error_size, "%s", "no Steam on this console");
	return 5; /* STEAM_BRIDGE_ITEM_FAILED */
}

/* ---------- MCC maps (port/linux/game/mcc_workshop.c, out with HALO_MCC 0) */

struct mcc_workshop_item;

/* (no MCC maps, so no map has a Workshop item or a title of one) */
int mcc_workshop_listing(char const name[128], struct mcc_workshop_item *item)
{
	(void)name;
	(void)item;
	return 0;
}

int mcc_workshop_map_title(char const *level, const void *catalog_name, char const *item_title, char *title,
	unsigned size)
{
	(void)level;
	(void)catalog_name;
	(void)item_title;
	(void)title;
	(void)size;
	return 0;
}
#endif
