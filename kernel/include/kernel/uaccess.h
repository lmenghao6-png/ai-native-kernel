#pragma once
#include <stdbool.h>
void uaccess_init(void);
bool copy_from_user(void *to, const void *from, uint64_t size);
bool copy_to_user(void *to, const void *from, uint64_t size);
