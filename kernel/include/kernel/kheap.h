#pragma once
#include <stdint.h>
void kheap_init(void);
void *kmalloc(uint64_t size);
void *kzalloc(uint64_t size);
