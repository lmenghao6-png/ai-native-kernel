#pragma once
#include <stdint.h>
void serial_init(void);
void serial_write_char(char ch);
void serial_write(const char *text);
void serial_write_hex_u64(uint64_t value);
void serial_write_u64(uint64_t value);
int serial_try_read(void);
