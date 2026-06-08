#pragma once
#include <stdint.h>
#include <stdbool.h>
struct task;
enum task_stop_reason { STOP_NONE, STOP_BLOCKED, STOP_PREEMPTED, STOP_EXITED };
void scheduler_init(uint32_t t);
void scheduler_submit(struct task *t);
void scheduler_tick(void);
