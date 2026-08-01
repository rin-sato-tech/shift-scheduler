# シフト自動作成デモアプリ データ定義書

## 1. 文書情報

- 文書名：シフト自動作成デモアプリ データ定義書
- 対象バージョン：MVP
- 対象システム：shift-scheduler
- 作成日：2026-08-01

## 2. データ設計方針

- データベースにはSQLiteを使用する
- 日付はISO 8601形式の文字列 `YYYY-MM-DD` で保存する
- 対象月は `YYYY-MM` 形式で扱う
- 真偽値はSQLite上では `0` または `1` で保存する
- シフト区分は `early` または `late` とする
- 従業員は原則として物理削除せず、有効状態で管理する
- シフト配置は1行を「1従業員・1日・1シフト」とする
- 希望休は1行を「1従業員・1日」とする
- 必要人数は1行を「1日・1シフト」とする
- データベースの制約とアプリケーション側の検証を併用する

## 3. エンティティ一覧

| テーブル名            | 論理名         | 概要                                                             |
| --------------------- | -------------- | ---------------------------------------------------------------- |
| employees             | 従業員         | 従業員の属性、責任者資格、契約勤務日数、勤務可能シフトを管理する |
| day_off_requests      | 希望休         | 従業員ごとの希望休日を管理する                                   |
| staffing_requirements | 必要人数       | 日付・シフトごとの必要人数と必要責任者数を管理する               |
| schedule_generations  | シフト生成履歴 | 対象月ごとの自動生成処理結果を管理する                           |
| schedules             | シフト配置     | 日付・シフト・従業員単位の配置結果を管理する                     |

## 4. employees

従業員の基本情報と、自動配置に必要な勤務条件を管理する。

| カラム名       | 型      | NULL | 制約        | 内容             |
| -------------- | ------- | ---- | ----------- | ---------------- |
| employee_id    | TEXT    | 不可 | PK          | 従業員ID         |
| name           | TEXT    | 不可 |             | 氏名             |
| is_manager     | INTEGER | 不可 | CHECK 0/1   | 責任者資格の有無 |
| contract_days  | INTEGER | 不可 | CHECK 0〜31 | 月間契約勤務日数 |
| can_work_early | INTEGER | 不可 | CHECK 0/1   | 早番勤務可否     |
| can_work_late  | INTEGER | 不可 | CHECK 0/1   | 遅番勤務可否     |
| is_active      | INTEGER | 不可 | CHECK 0/1   | 有効状態         |
| created_at     | TEXT    | 不可 |             | 作成日時         |
| updated_at     | TEXT    | 不可 |             | 更新日時         |

### 業務制約

- `employee_id`は一意とする
- `name`は空文字不可とする
- `contract_days`は0以上31以下とする
- `can_work_early`と`can_work_late`の少なくとも一方を1とする
- 無効な従業員は新規シフト生成の対象外とする

## 5. day_off_requests

従業員ごとの希望休日を管理する。

| カラム名           | 型      | NULL | 制約              | 内容     |
| ------------------ | ------- | ---- | ----------------- | -------- |
| day_off_request_id | INTEGER | 不可 | PK, AUTOINCREMENT | 希望休ID |
| employee_id        | TEXT    | 不可 | FK                | 従業員ID |
| target_date        | TEXT    | 不可 |                   | 希望休日 |
| created_at         | TEXT    | 不可 |                   | 作成日時 |

### 一意制約

- `employee_id`と`target_date`の組み合わせを一意とする

### 外部キー

- `employee_id`は`employees.employee_id`を参照する

### 業務制約

- 対象日は有効な日付であること
- 希望休は1日単位とする
- シフト区分別の希望休はMVPでは扱わない

## 6. staffing_requirements

日付・シフトごとの必要人数と必要責任者数を管理する。

| カラム名                | 型      | NULL | 制約              | 内容           |
| ----------------------- | ------- | ---- | ----------------- | -------------- |
| staffing_requirement_id | INTEGER | 不可 | PK, AUTOINCREMENT | 必要人数設定ID |
| target_date             | TEXT    | 不可 |                   | 対象日         |
| shift_type              | TEXT    | 不可 | CHECK             | シフト区分     |
| required_count          | INTEGER | 不可 | CHECK 0以上       | 必要人数       |
| required_manager_count  | INTEGER | 不可 | CHECK 0以上       | 必要責任者数   |
| created_at              | TEXT    | 不可 |                   | 作成日時       |
| updated_at              | TEXT    | 不可 |                   | 更新日時       |

### シフト区分

- `early`
- `late`

### 一意制約

- `target_date`と`shift_type`の組み合わせを一意とする

### 業務制約

- `required_manager_count`は`required_count`以下とする

## 7. schedule_generations

シフト自動生成処理の実行結果を管理する。

| カラム名        | 型      | NULL | 制約              | 内容             |
| --------------- | ------- | ---- | ----------------- | ---------------- |
| generation_id   | INTEGER | 不可 | PK, AUTOINCREMENT | 生成履歴ID       |
| target_month    | TEXT    | 不可 |                   | 対象月           |
| solver_status   | TEXT    | 不可 | CHECK             | Solverの結果     |
| objective_value | INTEGER | 可   |                   | 目的関数値       |
| max_deviation   | INTEGER | 可   |                   | 最大契約日数乖離 |
| total_deviation | INTEGER | 可   |                   | 契約日数乖離合計 |
| generated_at    | TEXT    | 不可 |                   | 生成日時         |

### solver_status

- `OPTIMAL`
- `FEASIBLE`
- `INFEASIBLE`
- `MODEL_INVALID`
- `UNKNOWN`

### 補足

- 解が存在しない場合、目的関数関連の値はNULLを許容する
- MVPでは生成履歴の一覧画面は必須ではない

## 8. schedules

月間シフトの配置結果を管理する。

1行は、1人・1日・1シフトの配置を表す。

| カラム名      | 型      | NULL | 制約              | 内容                 |
| ------------- | ------- | ---- | ----------------- | -------------------- |
| schedule_id   | INTEGER | 不可 | PK, AUTOINCREMENT | シフト配置ID         |
| generation_id | INTEGER | 可   | FK                | 生成履歴ID           |
| target_date   | TEXT    | 不可 |                   | 勤務日               |
| shift_type    | TEXT    | 不可 | CHECK             | シフト区分           |
| employee_id   | TEXT    | 不可 | FK                | 配置従業員ID         |
| is_manual     | INTEGER | 不可 | CHECK 0/1         | 手動変更された配置か |
| created_at    | TEXT    | 不可 |                   | 作成日時             |
| updated_at    | TEXT    | 不可 |                   | 更新日時             |

### 外部キー

- `generation_id`は`schedule_generations.generation_id`を参照する
- `employee_id`は`employees.employee_id`を参照する

### 一意制約

- `target_date`と`employee_id`の組み合わせを一意とする

### 業務制約

- 同一従業員を同じ日に複数のシフトへ登録しない
- 1日1シフト制約はデータベースとアプリケーションの両方で検証する
- 自動生成された配置は`is_manual = 0`とする
- 手動で追加された配置は`is_manual = 1`とする

## 9. テーブル関係

```text
employees
  ├── day_off_requests
  └── schedules

schedule_generations
  └── schedules

staffing_requirements
  └── 日付・シフトを通じてschedulesと論理的に対応
```

### 関係

- 1人の従業員は複数の希望休を持つ
- 1人の従業員は複数のシフト配置を持つ
- 1回の自動生成処理は複数のシフト配置を持つ
- 必要人数設定とシフト配置は日付・シフト区分で対応する

関係を簡略化すると次のようになります。

```text
employees 1 ── N day_off_requests
employees 1 ── N schedules
schedule_generations 1 ── N schedules
```

## 10. 更新・削除方針

### employees

- 従業員は原則として物理削除しない
- 利用停止時は`is_active = 0`とする
- 従業員IDは登録後に原則変更しない

### day_off_requests

- 希望休は画面から物理削除可能とする
- 従業員削除は原則発生しないため、外部キーは`ON DELETE RESTRICT`とする

### staffing_requirements

- 対象月の設定を再作成する場合は、対象月分を削除して再登録できる
- 日別変更ではUPDATEを使用する

### schedules

- 対象月を再生成する場合、既存の対象月シフトを削除して新規保存する
- 手動変更では個別追加・削除を行う

### schedule_generations

- 生成履歴を削除する場合、関連シフトは削除しない
- `generation_id`はNULLへ変更できる構造とする

## 11. サンプルデータ方針

### 従業員

- 従業員数：10人
- 責任者：4人
- 一般従業員：6人
- 契約勤務日数：10〜22日程度
- 早番のみ勤務可：1〜2人
- 遅番のみ勤務可：1〜2人
- 両方勤務可：残りの従業員

### 必要人数

- 原則、早番2人・遅番2人
- 必要責任者数は各シフト1人

### 希望休

- 1人あたり月2〜4日程度
- 特定日に希望休が集中するケースも用意する

### テスト用異常データ

- 責任者候補が不足する日
- 勤務可能者が不足する日
- 契約勤務日数合計と必要勤務枠が大きく異なるケース

## 12. 日付・日時の扱い

### DB保存形式

| 種類   | 保存形式   | 例                        |
| ------ | ---------- | ------------------------- |
| 日付   | YYYY-MM-DD | 2026-08-01                |
| 対象月 | YYYY-MM    | 2026-08                   |
| 日時   | ISO 8601   | 2026-08-01T00:30:00+09:00 |

### アプリ内

- 日付は`datetime.date`で扱う
- 日時は`datetime.datetime`で扱う
- DB登録時に文字列へ変換する
- DB取得後、必要な箇所で日付型へ変換する
