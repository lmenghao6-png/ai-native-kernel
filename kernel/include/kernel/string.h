#pragma once
#include <stdint.h>
void *memcpy(void *d, const void *s, uint64_t n);
void *memset(void *s, int c, uint64_t n);
int memcmp(const void *a, const void *b, uint64_t n);
uint64_t strlen(const char *s);
