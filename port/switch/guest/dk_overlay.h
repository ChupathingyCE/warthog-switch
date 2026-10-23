/*
DK_OVERLAY.H

What the overlay's drawing (ui_overlay_dk.c) asks of the deko3d device
(d3d8_dk.c): a draw of its gathered vertices over the back buffer, with its
own shaders and images, at the frame's Present.
*/

#ifndef __DK_OVERLAY_H
#define __DK_OVERLAY_H

#include <stdint.h>

struct dk_overlay_draw
{
	/* the vertices, triangles, each stride bytes: float position (window
	pixels from the top left), float texture coordinate, float shape (four),
	float edge (two), four bytes of color (red first) */
	const void *vertices;
	unsigned long count;
	unsigned long stride;
	/* the shaders' handles (host_dk_shader_find) */
	uint32_t vertex_shader;
	uint32_t pixel_shader;
	/* the texture cache's image numbers at the fragment stage's bindings 0,
	1 and 2 */
	uint32_t textures[3];
	/* places left for the game's own drawing (x0, y0, x1, y1 in window
	pixels from the top; all zero for none) */
	float cutouts[4][4];
	/* the back buffer's pixels */
	int window_width;
	int window_height;
};

/* draws over the back buffer with the state the overlay needs (blended, no
depth or stencil test, the whole target), and forgets the state the device
told the host, which the game's next draw tells again. 0 when there is no
back buffer to draw into. */
int dk_overlay_draw(const struct dk_overlay_draw *draw);

/* xbox_textures_dk.c: an image number of the texture cache's, reserved for
good (0: none left) */
uint32_t dk_texture_id_reserve(void);

#endif
