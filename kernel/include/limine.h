#ifndef LIMINE_H
#define LIMINE_H 1

#include <stdint.h>

/*
 * Minimal Limine protocol definitions used by Bastion. Constants and layouts
 * follow the upstream 0BSD limine-protocol header.
 */
#define LIMINE_REQUESTS_START_MARKER { \
    UINT64_C(0xf6b8f4b39de7d1ae), UINT64_C(0xfab91a6940fcb9cf), \
    UINT64_C(0x785c6ed015d3e316), UINT64_C(0x181e920a7852b9d9) \
}
#define LIMINE_REQUESTS_END_MARKER { \
    UINT64_C(0xadc0e0531bb10d03), UINT64_C(0x9572709f31764c62) \
}
#define LIMINE_BASE_REVISION(N) { \
    UINT64_C(0xf9562b2d5c95a6c8), UINT64_C(0x6a7b384944536bdc), (N) \
}
#define LIMINE_BASE_REVISION_SUPPORTED(VAR) ((VAR)[2] == 0)

#define LIMINE_COMMON_MAGIC \
    UINT64_C(0xc7b1dd30df4c8b88), UINT64_C(0x0a82e883a194f07b)
#define LIMINE_MEMMAP_REQUEST_ID { \
    LIMINE_COMMON_MAGIC, UINT64_C(0x67cf3d9d378a806f), \
    UINT64_C(0xe304acdfc50c3c62) \
}
#define LIMINE_HHDM_REQUEST_ID { \
    LIMINE_COMMON_MAGIC, UINT64_C(0x48dcf1cb8ad2b852), \
    UINT64_C(0x63984e959a98244b) \
}

#define LIMINE_MEMMAP_USABLE                 0
#define LIMINE_MEMMAP_RESERVED               1
#define LIMINE_MEMMAP_ACPI_RECLAIMABLE       2
#define LIMINE_MEMMAP_ACPI_NVS               3
#define LIMINE_MEMMAP_BAD_MEMORY             4
#define LIMINE_MEMMAP_BOOTLOADER_RECLAIMABLE 5
#define LIMINE_MEMMAP_EXECUTABLE_AND_MODULES 6
#define LIMINE_MEMMAP_FRAMEBUFFER            7

struct limine_memmap_entry {
    uint64_t base;
    uint64_t length;
    uint64_t type;
};

struct limine_memmap_response {
    uint64_t revision;
    uint64_t entry_count;
    struct limine_memmap_entry **entries;
};

struct limine_memmap_request {
    uint64_t id[4];
    uint64_t revision;
    struct limine_memmap_response *response;
};

struct limine_hhdm_response {
    uint64_t revision;
    uint64_t offset;
};

struct limine_hhdm_request {
    uint64_t id[4];
    uint64_t revision;
    struct limine_hhdm_response *response;
};

#endif
