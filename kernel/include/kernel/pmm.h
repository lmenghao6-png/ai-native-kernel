#pragma once
#include <stdint.h>
#include <stdbool.h>

struct limine_memmap_response;

typedef struct {
    uint64_t total_pages;
    uint64_t free_pages;
    uint64_t highest_page;
} pmm_stats_t;

bool pmm_init(const struct limine_memmap_response *memmap);
uint64_t pmm_alloc(void);
pmm_stats_t pmm_get_stats(void);
