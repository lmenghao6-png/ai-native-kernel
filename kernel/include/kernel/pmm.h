#pragma once
#include <stdint.h>
#include <stdbool.h>

struct limine_memmap_response;

#define PMM_PAGE_SIZE 4096ULL
#define PMM_BITMAP_BYTES 131072ULL
#define PMM_MAX_PAGES (PMM_BITMAP_BYTES * 8)

typedef struct {
    uint64_t total_pages;
    uint64_t free_pages;
    uint64_t highest_page;
} pmm_stats_t;

bool pmm_init(const struct limine_memmap_response *memmap);
uint64_t pmm_alloc(void);
bool pmm_free(uint64_t physical_address);
bool pmm_self_test(void);
pmm_stats_t pmm_get_stats(void);
