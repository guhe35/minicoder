# 演示任务：实现依赖感知的迭代任务调度器

当前项目用于为一个软件迭代生成可执行的任务波次，但现有实现只会把所有任务放进同一波，且报告功能尚未完成。

请按以下顺序完成任务：

1. 先运行 `python -m unittest discover -s tests -v`，复现并阅读现有失败。
2. 检查 `sprint_planner/planner.py`、`sprint_planner/report.py`、测试和 `demo.py`。
3. 完成 `build_execution_plan(tasks)`：
   - 输入是任务字典列表，每项包含非空字符串 `id`、`title`，以及 `priority`、`depends_on`、`done`。
   - `priority` 仅允许 `high`、`medium`、`low`。
   - 拒绝重复 ID、缺失依赖、自依赖和循环依赖，统一抛出 `PlanningError`。
   - 已完成任务不出现在结果中，但视为已经满足的依赖。
   - 每一波只能包含依赖已经在更早波次完成的待办任务。
   - 同一波内按优先级 high→medium→low 排序，相同优先级按 ID 升序。
   - 返回任务的深拷贝，不能修改输入，也不能让调用方通过结果修改原数据。
4. 完成 `render_markdown_plan(waves)`：
   - 标题固定为 `# Sprint Execution Plan`。
   - 每波使用 `## Wave N`，任务使用 `- [HIGH] id — title` 格式。
   - 末尾输出 `Summary: X pending task(s) across Y wave(s).`。
   - 空计划输出标题和 `No pending tasks.`。
5. 保留现有测试，并至少补充 2 个有意义的边界测试。
6. 运行全部测试，再运行 `python demo.py`；只有最新代码通过验证后才能结束。

请保持公开函数签名不变，不引入第三方依赖。最终用中文总结修改文件、算法思路、失败修复过程和验证结果。
