# 双台架备用接线复核台

电测实验室的白班站员从北、南两台架导入实测线表。复测员更正线表，站员按交班指定的修订发行固定件。中心收件员按名册核对两站来件，登记员固定具名备用线。夜班在站库关闭后按实际收件复核，次班接线负责人按报告号核账。总数大于零且双用数等于总数，才表示两条指定线在每个可用方案中都要保留。

## 业务口径

两站每批声明同一组三个公开端子，端子按名字合为同一顶点。私有接点、原线号及线表只存本站。每个内部接点必须经原线到达至少一个公开端子。原线号在单份修订内唯一。原线与备用线都是无向线，平行线按身份分别参与。端点归并后落在同一顶点的线形成自环，无法参加合格方案。一个方案按线身份选取，覆盖全部接点并连成一体且无回路。两项计数分别是全部方案数和同一方案同时使用指定两线的数量，都是精确非负整数。合法断开的输入签出 0、0。

站库各自使用 SQLite，包含不可变修订、当前指针与原始发行件。合法勘误以同批同站的已归档修订为父版，保存完整新表并推进当前指针。中心库单独存放批次名册、实收、固定清单、定稿和首执。更正清单会得到新号。错误来件与错误请求没有新成果。报告和首执在同一事务内生效，领取读取已存定稿。中心核算只需要中心库。重复初始化补建缺少的表及批次，保留已存在的名册及业务记录。

## 核验与演示

使用 Python 3.11 标准库。在项目根目录运行控制台物化提供的 `python3 -B check_project.py` 执行完整 `tests` 回归。运行 `python3 -B -m review.cli demo` 完成独立临时目录内的交班。演示移走两个站库后签出两份报告，再按号领取。`samples/` 包含北站星形及端子链两版线表、南站仅端子线表和同批中心名册及清单。星形四类方案按都不用、仅第一条、仅第二条、同时使用分为 1、2、2、3。端子链对应 1、1、1、1。

## 操作入口

每行命令独立执行。`init` 输出中心库和各站库路径，其余参数中的大写名称代入操作获得的实际值。北站勘误使用 `--table corrected --parent REVISION`。`freeze` 和 `reissue` 把原件写入指定文件，`receive` 读取该文件。复核请求保留两实收号与两线号的提交顺序。CLI 以十进制整数字符串显示计数，Python API 返回 `int`。

```text
python3 -B -m review.cli init bench samples/center.json
python3 -B -m review.cli record STATION_DB samples/north.json
python3 -B -m review.cli freeze STATION_DB north REVISION north.v1
python3 -B -m review.cli reissue STATION_DB FREEZE north-copy.v1
python3 -B -m review.cli receive CENTER_DB night-01 north north.v1
python3 -B -m review.cli links CENTER_DB samples/center.json
python3 -B -m review.cli review CENTER_DB RECEIPT_1 RECEIPT_2 LIST p q
python3 -B -m review.cli get CENTER_DB REPORT
```

## Python 接口

| 模块 | 调用与结果 |
| --- | --- |
| `survey.capture` | `record_revision(store, station, batch, parent_id, terminals, line_table)` 返回修订号。首版传 `None`，`line_table` 含 `junctions` 及 `wires`，后者每行为 `[线号, 端点, 端点]`。 |
| `issue.dispatch` | `freeze_package(revisions, issues, station, revision_id)` 返回 `IssuedPackage`。`get_package(issues, freeze_id)` 返回已存的同一记录，含 `raw`、`revision_id` 和 `freeze_id`。 |
| `intake.receipts` | `receive_package(inbox, batch, station, raw)` 返回实收号。冻结号绑定原字节与出处。 |
| `links.fixed_list` | `freeze_links(inbox, catalog, batch, rows)` 返回固定清单号。每行含 `id` 以及两端 `a`、`b`，每端为 `[站别, 端子名]`。 |
| `review.publication` | `issue_report(inbox, catalog, reports, receipt_ids, list_id, selected)` 返回 `SignedReport`。`get_report(reports, report_id)` 返回持久化的同一值及 `receipt` 原字节。 |

各存储对象接收 SQLite 路径，通过自身 `initialize` 或 `review.cli.initialize_workspace(root, manifests)` 建表。首次登记批次时使用 `BatchManifest.from_mapping(batch, stations)` 构建两个名册项。输入及归属错误抛出 `ValueError`，未知持久化标识抛出 `LookupError`，数据库错误保留 SQLite 例外。发布成功时报告包含实际清单号、所选线号及按调用顺序排列的父件，父件记录冻结号、修订号及原来件 SHA-256。首执包含报告号和已存报告正文的 SHA-256，便于核验领取的定稿。

## V1 来件

原件是 UTF-8 JSON 对象。外层字段为 `version`、`freeze_id`、`batch`、`station`、`revision_id`、`terminals`、`evidence`，版本为整数 `1`。中心核对该件的声明与批次名册，保存收到的原字节。发行的正文是 `forests` 数组，各项包含端子 `groups` 和正整数重数 `count`。每组对应一棵覆盖相应端子和其本地接点的树，每个本地连通块都接到至少一个端子。各组共同覆盖三端子，组之间无重复端子，重数用带 `0x` 前缀的小写十六进制编码，避免十进制转换限制。南站仅端子时正文可写为 `{"forests":[{"groups":[["A"],["B"],["C"]],"count":"0x1"}]}`。实收保全外层和正文的全部原字节。
