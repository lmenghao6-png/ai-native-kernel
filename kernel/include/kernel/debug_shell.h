#pragma once
void debug_shell_init(void);
void debug_shell_run_forever(void) __attribute__((noreturn));
void debug_shell_poll(void);
