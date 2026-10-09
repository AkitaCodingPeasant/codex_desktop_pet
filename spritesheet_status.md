## spritesheet status
```
第  0 列： Idle_1，25 格
第  1 列： Idle_2_1，38 格
第  2 列： Idle_2_2，38 格
第  3 列： Idle_3，29 格
第  4 列： Idle_4，28 格
第  5 列： Thinking_1_1，25 格
第  6 列： Thinking_1_2，25 格
第  7 列： Success intro，21 格
第  8 列： Success repeat，9 格
第  9 列： Asking intro，29 格
第 10 列： Asking repeat，32 格
第 11 列： Failed intro，16 格
第 12 列： Failed repeat，19 格
第 13 列： Cancelled intro，5 格
第 14 列： Cancelled repeat，36 格
第 15 列： Working intro，59 格
第 16 列： Working repeat，60 格
```

## gpt hook
預設狀態
→ 桌寵：Idle
隨機從 Idle_1、Idle_2、Idle_3、Idle_4 播放
Idle_2_1 和 Idle_2_2 加在一起就是 Idle_2

turn.in_progress
→ 桌寵：Thinking
撥放 Thinking
Thinking_1_1 和 Thinking_1_2 加在一起就是 Thinking

tool.started
→ 桌寵：Working
撥放 Working intro 一次，接著循環撥放 Working repeat，直到工具執行結束
Working 優先於 Thinking，低於 Asking 與結果動畫

action_required
→ 桌寵：Asking
撥放 Asking intro
Asking intro 完成後連續撥放 Asking repeat

turn.completed
→ 桌寵：Success
撥放 Success intro
Success intro 完成後連續撥放 Success repeat 3 次

turn.failed
→ 桌寵：Failed
撥放 Failed intro
Failed intro 完成後連續撥放 Failed repeat 3 次

turn.cancelled
→ 桌寵：Cancelled
撥放 Cancelled intro
Cancelled intro 完成後撥放 Cancelled repeat 1 次

