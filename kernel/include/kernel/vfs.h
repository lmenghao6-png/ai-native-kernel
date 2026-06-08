#pragma once
#include <stdint.h>
#include <stddef.h>
#define VFS_MAX_NAME 128
#define VFS_MAX_NODES 256
typedef enum { VFS_FILE, VFS_DIRECTORY } vfs_type_t;
typedef struct vfs_node { char name[VFS_MAX_NAME]; vfs_type_t type; size_t size; uint8_t *data; struct vfs_node *parent,*children,*next; } vfs_node_t;
typedef struct { vfs_node_t *node; size_t offset; } vfs_file_t;
void vfs_init(void);
vfs_node_t *vfs_lookup(const char *path);
vfs_file_t *vfs_open(const char *path);
int vfs_read(vfs_file_t *f, void *b, size_t s);
void vfs_close(vfs_file_t *f);
vfs_node_t *vfs_create_node(const char *n, vfs_type_t t);
void vfs_attach(vfs_node_t *p, vfs_node_t *c);
void vfs_dump(vfs_node_t *n, int d);
