#include "kernel/vfs.h"
#include "kernel/string.h"
#include "kernel/kheap.h"
#include "kernel/serial.h"
static vfs_node_t *root = 0;
static vfs_node_t pool[VFS_MAX_NODES];
static int count = 0;
void vfs_init(void) {
    count = 0;
    for(int i=0;i<VFS_MAX_NODES;i++){pool[i].name[0]=0;pool[i].children=0;pool[i].next=0;}
    root=vfs_create_node("/",VFS_DIRECTORY); root->parent=root;
    serial_write("[vfs] initialized\n");
}
vfs_node_t *vfs_create_node(const char *n, vfs_type_t t) {
    if(count>=VFS_MAX_NODES)return 0;
    vfs_node_t *nd=&pool[count++]; int i=0;
    while(n[i]&&i<VFS_MAX_NAME-1){nd->name[i]=n[i];i++;}
    nd->name[i]=0; nd->type=t; nd->size=0; nd->data=0; nd->children=0; nd->next=0;
    return nd;
}
void vfs_attach(vfs_node_t *p, vfs_node_t *c){if(!p||!c)return;c->parent=p;c->next=p->children;p->children=c;}
vfs_node_t *vfs_lookup(const char *path) {
    if(!path||!path[0])return 0;
    vfs_node_t *cur=root;
    if(path[0]=='/'&&path[1]==0)return root;
    int i=path[0]=='/'?1:0;
    while(path[i]){
        char name[VFS_MAX_NAME]; int j=0;
        while(path[i]&&path[i]!='/'&&j<VFS_MAX_NAME-1)name[j++]=path[i++];
        name[j]=0; if(path[i]=='/')i++;
        vfs_node_t *c=cur->children; int found=0;
        while(c){int m=1;for(int k=0;name[k]||c->name[k];k++)if(name[k]!=c->name[k]){m=0;break;}if(m){cur=c;found=1;break;}c=c->next;}
        if(!found)return 0;
    }
    return cur;
}
vfs_file_t *vfs_open(const char *path){vfs_node_t *n=vfs_lookup(path);if(!n||n->type!=VFS_FILE)return 0;vfs_file_t *f=kmalloc(sizeof(*f));if(!f)return 0;f->node=n;f->offset=0;return f;}
int vfs_read(vfs_file_t *f, void *b, size_t s){if(!f||!f->node||!f->node->data||!b)return-1;if(f->offset>=f->node->size)return 0;size_t r=f->node->size-f->offset;size_t t=s<r?s:r;memcpy(b,f->node->data+f->offset,t);f->offset+=t;return(int)t;}
void vfs_close(vfs_file_t *f){(void)f;}
void vfs_dump(vfs_node_t *n,int d){if(!n)n=root;for(int i=0;i<d;i++)serial_write("  ");serial_write(n->type==VFS_DIRECTORY?"[DIR] ":"[FILE] ");serial_write(n->name);serial_write("\n");vfs_node_t *c=n->children;while(c){vfs_dump(c,d+1);c=c->next;}}
