#include "kernel/initramfs.h"
#include "kernel/vfs.h"
#include "kernel/serial.h"
#include "kernel/string.h"
#include <stdint.h>

#define CPIO_HEADER_SIZE 110
#define CPIO_MODE_TYPE_MASK 0170000
#define CPIO_MODE_DIRECTORY 0040000
#define CPIO_MODE_REGULAR 0100000

static size_t align4(size_t value) {
    return (value + 3) & ~(size_t)3;
}

static bool add_size(size_t a, size_t b, size_t *result) {
    if (a > (size_t)-1 - b) {
        return false;
    }
    *result = a + b;
    return true;
}

static bool parse_hex8(const uint8_t *text, uint32_t *value) {
    uint32_t result = 0;
    for (int i = 0; i < 8; i++) {
        uint8_t ch = text[i];
        uint8_t digit;
        if (ch >= '0' && ch <= '9') {
            digit = ch - '0';
        } else if (ch >= 'a' && ch <= 'f') {
            digit = ch - 'a' + 10;
        } else if (ch >= 'A' && ch <= 'F') {
            digit = ch - 'A' + 10;
        } else {
            return false;
        }
        result = (result << 4) | digit;
    }
    *value = result;
    return true;
}

static bool string_equal(const char *a, const char *b) {
    while (*a && *b && *a == *b) {
        a++;
        b++;
    }
    return *a == *b;
}

static vfs_node_t *find_child(vfs_node_t *parent, const char *name) {
    for (vfs_node_t *child = parent->children; child; child = child->next) {
        if (string_equal(child->name, name)) {
            return child;
        }
    }
    return 0;
}

static vfs_node_t *ensure_path(const char *path, vfs_type_t final_type) {
    vfs_node_t *current = vfs_lookup("/");
    size_t index = 0;

    while (path[index] == '/') {
        index++;
    }
    if (path[index] == '.' && path[index + 1] == '/') {
        index += 2;
    }
    if (!path[index]) {
        return current;
    }

    while (path[index]) {
        char component[VFS_MAX_NAME];
        size_t length = 0;
        while (path[index] && path[index] != '/') {
            if (length + 1 >= sizeof(component)) {
                return 0;
            }
            component[length++] = path[index++];
        }
        component[length] = 0;
        while (path[index] == '/') {
            index++;
        }

        bool is_last = path[index] == 0;
        vfs_node_t *child = find_child(current, component);
        if (!child) {
            child = vfs_create_node(
                component,
                is_last ? final_type : VFS_DIRECTORY
            );
            if (!child) {
                return 0;
            }
            vfs_attach(current, child);
        } else if (!is_last && child->type != VFS_DIRECTORY) {
            return 0;
        }

        current = child;
    }

    current->type = final_type;
    return current;
}

bool initramfs_load(void *start, size_t size) {
    uint8_t *archive = start;
    size_t offset = 0;
    uint64_t entries = 0;

    while (offset < size) {
        size_t header_end;
        if (!add_size(offset, CPIO_HEADER_SIZE, &header_end) ||
            header_end > size) {
            serial_write("[initramfs] truncated header\n");
            return false;
        }

        uint8_t *header = archive + offset;
        if (memcmp(header, "070701", 6) != 0 &&
            memcmp(header, "070702", 6) != 0) {
            serial_write("[initramfs] invalid newc magic\n");
            return false;
        }

        uint32_t mode;
        uint32_t file_size;
        uint32_t name_size;
        if (!parse_hex8(header + 14, &mode) ||
            !parse_hex8(header + 54, &file_size) ||
            !parse_hex8(header + 94, &name_size) ||
            name_size == 0) {
            serial_write("[initramfs] invalid header fields\n");
            return false;
        }

        size_t name_end;
        if (!add_size(header_end, name_size, &name_end) || name_end > size) {
            serial_write("[initramfs] truncated filename\n");
            return false;
        }

        char *name = (char *)(archive + header_end);
        if (name[name_size - 1] != 0) {
            serial_write("[initramfs] unterminated filename\n");
            return false;
        }
        if (string_equal(name, "TRAILER!!!")) {
            serial_write("[initramfs] mounted ");
            serial_write_u64(entries);
            serial_write(" entries\n");
            return true;
        }

        size_t data_offset = align4(name_end);
        size_t data_end;
        if (!add_size(data_offset, file_size, &data_end) || data_end > size) {
            serial_write("[initramfs] truncated file data\n");
            return false;
        }

        uint32_t file_type = mode & CPIO_MODE_TYPE_MASK;
        if (!string_equal(name, ".") &&
            !string_equal(name, "./") &&
            (file_type == CPIO_MODE_DIRECTORY ||
             file_type == CPIO_MODE_REGULAR)) {
            vfs_type_t type = file_type == CPIO_MODE_DIRECTORY
                ? VFS_DIRECTORY
                : VFS_FILE;
            vfs_node_t *node = ensure_path(name, type);
            if (!node) {
                serial_write("[initramfs] VFS capacity exceeded\n");
                return false;
            }
            if (type == VFS_FILE) {
                node->data = archive + data_offset;
                node->size = file_size;
            }
            entries++;
        }

        offset = align4(data_end);
    }

    serial_write("[initramfs] missing trailer\n");
    return false;
}

void initramfs_dump(void) {
    vfs_dump(vfs_lookup("/"), 0);
}
