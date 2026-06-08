#pragma once
#include <stdint.h>
#include <stdbool.h>
typedef struct { uint64_t total_pages; uint64_t free_pages; } pmm_stats_t;
void pmm_init(void *memmap_response);
uint64_t pmm_alloc(void);
pmm_stats_t pmm_get_stats(void);
