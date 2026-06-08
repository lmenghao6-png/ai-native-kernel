#pragma once
#include <stddef.h>
#include <stdbool.h>

bool initramfs_load(void *start, size_t size);
void initramfs_dump(void);
