#include "kernel/elf.h"
#include "kernel/vfs.h"
#include "kernel/serial.h"
#include "kernel/string.h"
#include "kernel/vmm.h"
#include <stddef.h>

#define ELFCLASS64 2
#define ELFDATA2LSB 1
#define EV_CURRENT 1
#define ET_EXEC 2
#define EM_X86_64 62
#define USER_MIN_ADDRESS 0x1000ULL
#define USER_MAX_ADDRESS 0x0000800000000000ULL
#define PAGE_SIZE 0x1000ULL

static bool range_within(uint64_t offset, uint64_t length, uint64_t size) {
    return offset <= size && length <= size - offset;
}

int elf_load(const char *path, uint64_t *entry_out) {
    if (!entry_out) {
        return -1;
    }
    *entry_out = 0;

    vfs_node_t *node = vfs_lookup(path);
    if (!node || node->type != VFS_FILE || !node->data ||
        node->size < sizeof(elf64_ehdr_t)) {
        serial_write("[elf] file not found or truncated\n");
        return -1;
    }

    elf64_ehdr_t *header = (elf64_ehdr_t *)node->data;
    if (memcmp(header->e_ident, "\x7f" "ELF", 4) != 0 ||
        header->e_ident[4] != ELFCLASS64 ||
        header->e_ident[5] != ELFDATA2LSB ||
        header->e_ident[6] != EV_CURRENT ||
        header->e_type != ET_EXEC ||
        header->e_machine != EM_X86_64 ||
        header->e_version != EV_CURRENT ||
        header->e_phentsize != sizeof(elf64_phdr_t) ||
        !range_within(
            header->e_phoff,
            (uint64_t)header->e_phnum * header->e_phentsize,
            node->size
        )) {
        serial_write("[elf] invalid ELF64 executable\n");
        return -1;
    }

    elf64_phdr_t *program_headers =
        (elf64_phdr_t *)(node->data + header->e_phoff);
    uint64_t loaded_segments = 0;

    for (uint16_t i = 0; i < header->e_phnum; i++) {
        elf64_phdr_t *segment = &program_headers[i];
        if (segment->p_type != PT_LOAD) {
            continue;
        }
        if (segment->p_filesz > segment->p_memsz ||
            !range_within(segment->p_offset, segment->p_filesz, node->size) ||
            segment->p_vaddr < USER_MIN_ADDRESS ||
            segment->p_vaddr >= USER_MAX_ADDRESS ||
            segment->p_memsz > USER_MAX_ADDRESS - segment->p_vaddr) {
            serial_write("[elf] invalid load segment\n");
            return -1;
        }
        if (segment->p_memsz == 0) {
            continue;
        }

        uint64_t first_page = segment->p_vaddr & ~(PAGE_SIZE - 1);
        uint64_t segment_end = segment->p_vaddr + segment->p_memsz;
        uint64_t last_page = (segment_end + PAGE_SIZE - 1) & ~(PAGE_SIZE - 1);
        uint64_t page_count = (last_page - first_page) / PAGE_SIZE;

        /*
         * Pages remain writable during this early loader phase. A later VMM
         * protection pass will apply the final ELF PF_W/PF_X permissions.
         */
        if (!vmm_map_new_pages(
                first_page,
                page_count,
                VMM_PAGE_USER | VMM_PAGE_WRITABLE,
                0)) {
            serial_write("[elf] page allocation failed\n");
            return -1;
        }

        memcpy(
            (void *)segment->p_vaddr,
            node->data + segment->p_offset,
            segment->p_filesz
        );
        memset(
            (void *)(segment->p_vaddr + segment->p_filesz),
            0,
            segment->p_memsz - segment->p_filesz
        );
        loaded_segments++;
    }

    if (loaded_segments == 0 ||
        header->e_entry < USER_MIN_ADDRESS ||
        header->e_entry >= USER_MAX_ADDRESS) {
        serial_write("[elf] no runnable load segments\n");
        return -1;
    }

    *entry_out = header->e_entry;
    serial_write("[elf] loaded ");
    serial_write(path);
    serial_write(" entry=");
    serial_write_hex_u64(*entry_out);
    serial_write("\n");
    return 0;
}
