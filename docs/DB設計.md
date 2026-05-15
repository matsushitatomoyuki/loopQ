# LoopQ データベース設計書

策定日：2026年5月
対象：PostgreSQL 15+（本番）/ SQLite（ローカル開発）
ORM：Django 5.2 ORM
方針：第3正規形 + 将来の業態拡大・データ販売・API/MCP連携・海外展開を見据えた拡張可能設計

---

## 1. 設計原則

1. **正規化（第3正規形）を徹底** — 重複データを持たない
2. **イベントログは絶対に削除しない** — 分析の原資
3. **論理削除を基本** — `is_deleted` または `deleted_at` で運用
4. **timestampはUTC保存** — 海外展開対応
5. **UUIDを主キーに採用** — 名寄せ・データ移行・分散対応
6. **JSONフィールドは集計結果や柔軟データのみ** — 検索対象はカラム化
7. **業態拡大可能** — `business_category` で飲食以外も収容
8. **多通貨・多言語対応** — `currency_code` / `locale` を最初から持つ
9. **クライアント識別の二重管理** — localStorage UUID + サーバー側 Client.id
10. **個人情報は最小限** — MVP は UUID のみ、連絡先は nullable

---

## 2. テーブル一覧（全体像）

### マスタ系
- `business_category` — 業態マスタ（飲食・カフェ・美容等）
- `currency` — 通貨マスタ
- `locale` — 言語・地域マスタ

### 店舗・店主系
- `owner` — 店主アカウント（Django authユーザー拡張）
- `store` — 店舗
- `store_staff` — 店舗スタッフ（複数店舗対応）
- `subscription_plan` — 料金プランマスタ
- `store_subscription` — 店舗の契約状態

### 来店客系
- `client` — 来店客（UUID識別）
- `client_identity` — 連絡先・SNS連携（LINE/メール/電話）
- `client_visit` — 来店記録

### アンケート系
- `survey_template` — 店舗別アンケート定義
- `question` — 設問マスタ
- `survey_response` — アンケート回答ヘッダ
- `answer` — 設問単位の回答

### ガチャ・クーポン系
- `roulette_config` — ルーレット設定（店舗別／プリセット）
- `roulette_prize` — 賞品マスタ（pt、確率）
- `roulette_spin` — ガチャ実行ログ
- `coupon` — クーポン発行・状態
- `coupon_usage` — クーポン使用記録

### PWA・通知系
- `pwa_install` — PWAインストール記録
- `notification` — 通知送信履歴
- `notification_quota` — 通知回数の月次制限管理

### イベントログ・分析系
- `event_log` — 全イベントを記録（最重要）
- `daily_metric` — 日次集計（バッチ生成）
- `monthly_metric` — 月次集計（バッチ生成）

---

## 3. マスタ系テーブル

### business_category（業態マスタ）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | SERIAL | PK | |
| code | VARCHAR(32) | UNIQUE NOT NULL | restaurant_ramen, cafe, beauty_salon 等 |
| name_ja | VARCHAR(64) | NOT NULL | 表示名（日本語） |
| name_en | VARCHAR(64) | | 表示名（英語） |
| frequency_type | VARCHAR(16) | NOT NULL | high / mid / low |
| active_metric | VARCHAR(8) | NOT NULL | WAU / MAU / QAU |
| created_at | TIMESTAMP | NOT NULL | |

**frequency_type と active_metric の対応**
- `high` → WAU（カフェ・ファストフード・ラーメン）
- `mid` → MAU（居酒屋・レストラン・定食屋）
- `low` → QAU（美容院・ファッション・高級店）

### currency（通貨マスタ）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| code | CHAR(3) | PK | JPY, USD, EUR（ISO 4217） |
| symbol | VARCHAR(8) | NOT NULL | ¥, $, € |
| decimal_places | SMALLINT | NOT NULL | 0（円）/ 2（ドル） |

### locale（言語・地域マスタ）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| code | VARCHAR(8) | PK | ja_JP, en_US |
| timezone | VARCHAR(64) | NOT NULL | Asia/Tokyo |
| country_code | CHAR(2) | NOT NULL | JP, US |

---

## 4. 店舗・店主系

### owner（店主アカウント）

Django `AbstractUser` を拡張する想定。

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | UUID | PK | |
| email | VARCHAR(255) | UNIQUE NOT NULL | ログインID |
| password | VARCHAR(128) | NOT NULL | Django auth ハッシュ |
| phone | VARCHAR(32) | | SMS 2段階認証用（課金プランで利用） |
| sms_2fa_enabled | BOOLEAN | NOT NULL DEFAULT FALSE | |
| is_active | BOOLEAN | NOT NULL DEFAULT TRUE | |
| last_login | TIMESTAMP | | |
| created_at | TIMESTAMP | NOT NULL | |

### store（店舗）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | UUID | PK | QR URLの一部に使う |
| owner_id | UUID | FK(owner) NOT NULL | |
| name | VARCHAR(128) | NOT NULL | |
| business_category_id | INT | FK(business_category) NOT NULL | |
| postal_code | VARCHAR(16) | | |
| address | VARCHAR(255) | | |
| latitude | DECIMAL(10,7) | | 商圏分析用 |
| longitude | DECIMAL(10,7) | | |
| currency_code | CHAR(3) | FK(currency) NOT NULL DEFAULT 'JPY' | |
| locale_code | VARCHAR(8) | FK(locale) NOT NULL DEFAULT 'ja_JP' | |
| logo_url | VARCHAR(512) | | |
| brand_color | CHAR(7) | | #RRGGBB |
| google_place_id | VARCHAR(128) | | クチコミ連携用 |
| instagram_handle | VARCHAR(64) | | |
| line_official_id | VARCHAR(64) | | |
| is_active | BOOLEAN | NOT NULL DEFAULT TRUE | |
| deleted_at | TIMESTAMP | | 論理削除 |
| created_at | TIMESTAMP | NOT NULL | |

**インデックス**：`(owner_id)`, `(business_category_id)`, `(latitude, longitude)`

### store_staff（店舗スタッフ）

店主以外がダッシュボードを見る場合。MVPでは未使用、テーブルだけ用意。

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | UUID | PK | |
| store_id | UUID | FK(store) NOT NULL | |
| owner_id | UUID | FK(owner) NOT NULL | |
| role | VARCHAR(16) | NOT NULL | manager / viewer |
| created_at | TIMESTAMP | NOT NULL | |

UNIQUE`(store_id, owner_id)`

### subscription_plan（料金プランマスタ）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | SERIAL | PK | |
| code | VARCHAR(32) | UNIQUE NOT NULL | free, standard, pro, app_basic 等 |
| name | VARCHAR(64) | NOT NULL | |
| monthly_price | INT | NOT NULL | 円。0=無料 |
| currency_code | CHAR(3) | FK(currency) NOT NULL | |
| active_limit | INT | | WAU/MAU/QAU上限。NULL=無制限 |
| features | JSONB | NOT NULL DEFAULT '{}' | 機能フラグ |
| is_active | BOOLEAN | NOT NULL DEFAULT TRUE | |

### store_subscription（店舗の契約状態）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | UUID | PK | |
| store_id | UUID | FK(store) NOT NULL | |
| plan_id | INT | FK(subscription_plan) NOT NULL | |
| started_at | TIMESTAMP | NOT NULL | |
| ended_at | TIMESTAMP | | NULL=継続中 |
| billing_status | VARCHAR(16) | NOT NULL | active / past_due / canceled |
| stripe_subscription_id | VARCHAR(128) | | 決済連携用 |
| created_at | TIMESTAMP | NOT NULL | |

**インデックス**：`(store_id, ended_at)` — 現行プラン取得用

---

## 5. 来店客系

### client（来店客）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | UUID | PK | localStorage と同期 |
| first_seen_at | TIMESTAMP | NOT NULL | 初回QRスキャン日時 |
| last_seen_at | TIMESTAMP | NOT NULL | |
| total_points | INT | NOT NULL DEFAULT 0 | 累計獲得pt |
| available_points | INT | NOT NULL DEFAULT 0 | 未使用残高 |
| locale_code | VARCHAR(8) | FK(locale) | ブラウザから推定 |
| created_at | TIMESTAMP | NOT NULL | |

**ポイント**：MVPでは認証なし。Phase 2以降に累計100pt超で連携誘導。

### client_identity（連絡先・SNS連携）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | UUID | PK | |
| client_id | UUID | FK(client) NOT NULL | |
| channel | VARCHAR(16) | NOT NULL | line / email / phone / google |
| identifier | VARCHAR(255) | NOT NULL | LINE userId / メールアドレス / 電話番号 |
| verified_at | TIMESTAMP | | 検証済みかどうか |
| created_at | TIMESTAMP | NOT NULL | |

UNIQUE`(channel, identifier)` — 名寄せ防止
**ポイント**：1人で複数チャネル登録可。名寄せはこのテーブルで実現。

### client_visit（来店記録）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | UUID | PK | |
| client_id | UUID | FK(client) NOT NULL | |
| store_id | UUID | FK(store) NOT NULL | |
| visited_at | TIMESTAMP | NOT NULL | |
| visit_number | INT | NOT NULL | この店舗での通算来店回数 |
| companions | SMALLINT | | 同伴人数（フェーズ1の回答から） |
| referral_source | VARCHAR(16) | | map / referral / regular / passerby |
| created_at | TIMESTAMP | NOT NULL | |

**インデックス**：`(client_id, store_id)`, `(store_id, visited_at)`

---

## 6. アンケート系

### survey_template（店舗別アンケート定義）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | UUID | PK | |
| store_id | UUID | FK(store) NOT NULL | |
| version | INT | NOT NULL | バージョン管理 |
| is_active | BOOLEAN | NOT NULL DEFAULT TRUE | |
| created_at | TIMESTAMP | NOT NULL | |

UNIQUE`(store_id, version)`

### question（設問マスタ）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | UUID | PK | |
| survey_template_id | UUID | FK(survey_template) NOT NULL | |
| phase | SMALLINT | NOT NULL | 1 or 2 |
| order_no | SMALLINT | NOT NULL | フェーズ内の表示順 |
| question_type | VARCHAR(16) | NOT NULL | choice / slider / boolean |
| body_i18n | JSONB | NOT NULL | {"ja":"...", "en":"..."} |
| options_i18n | JSONB | | 選択肢の多言語データ |
| is_required | BOOLEAN | NOT NULL DEFAULT TRUE | |

UNIQUE`(survey_template_id, phase, order_no)`

### survey_response（アンケート回答ヘッダ）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | UUID | PK | |
| client_id | UUID | FK(client) NOT NULL | |
| store_id | UUID | FK(store) NOT NULL | |
| survey_template_id | UUID | FK(survey_template) NOT NULL | |
| visit_id | UUID | FK(client_visit) | |
| phase1_completed_at | TIMESTAMP | | |
| phase2_completed_at | TIMESTAMP | | NULL=未完 |
| total_duration_sec | INT | | 開始〜完了の秒数 |
| created_at | TIMESTAMP | NOT NULL | |

**インデックス**：`(store_id, created_at)`

### answer（設問単位の回答）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | UUID | PK | |
| survey_response_id | UUID | FK(survey_response) NOT NULL | |
| question_id | UUID | FK(question) NOT NULL | |
| value_int | SMALLINT | | スライダー値 1〜5 |
| value_text | VARCHAR(64) | | 選択肢コード |
| answered_at | TIMESTAMP | NOT NULL | |

UNIQUE`(survey_response_id, question_id)`

---

## 7. ガチャ・クーポン系

### roulette_config（ルーレット設定）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | UUID | PK | |
| store_id | UUID | FK(store) | NULL=システムデフォルト |
| name | VARCHAR(64) | NOT NULL | |
| is_active | BOOLEAN | NOT NULL DEFAULT TRUE | |
| created_at | TIMESTAMP | NOT NULL | |

### roulette_prize（賞品マスタ）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | UUID | PK | |
| roulette_config_id | UUID | FK(roulette_config) NOT NULL | |
| points | INT | NOT NULL | 100, 300, 500, 1000, 3000, 10000 |
| probability_bp | INT | NOT NULL | basis point（10000=100%）。例：7000=70% |
| expiry_days | INT | | 1000pt以上のみ30日等。NULL=無期限 |
| rarity | VARCHAR(16) | NOT NULL | normal / rare / super_rare / legendary |

**確率はbasis point（10000=100%）で持つ** — 浮動小数の累積誤差を避けるため。
合計 = 10000 になることをアプリケーション側で検証。

### roulette_spin（ガチャ実行ログ）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | UUID | PK | |
| client_id | UUID | FK(client) NOT NULL | |
| store_id | UUID | FK(store) NOT NULL | |
| survey_response_id | UUID | FK(survey_response) NOT NULL | |
| prize_id | UUID | FK(roulette_prize) NOT NULL | |
| points_awarded | INT | NOT NULL | 当選pt（賞品の値をデノーマライズ保持） |
| spun_at | TIMESTAMP | NOT NULL | |

UNIQUE`(survey_response_id)` — 1回答=1回転を強制

### coupon（クーポン発行・状態）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | UUID | PK | |
| client_id | UUID | FK(client) NOT NULL | |
| store_id | UUID | FK(store) NOT NULL | |
| roulette_spin_id | UUID | FK(roulette_spin) NOT NULL | |
| points | INT | NOT NULL | |
| status | VARCHAR(16) | NOT NULL | issued / activated / used / expired |
| issued_at | TIMESTAMP | NOT NULL | |
| expires_at | TIMESTAMP | | NULL=無期限 |
| activated_at | TIMESTAMP | | 「使う」ボタン押下時刻 |
| used_at | TIMESTAMP | | 店舗確認完了時刻 |

UNIQUE`(roulette_spin_id)`
**インデックス**：`(client_id, status)`, `(store_id, status)`

**status遷移**
- `issued` → ガチャで発行
- `activated` → 客が「使う」を押した（5分カウントダウン開始）
- `used` → 店主確認完了 or 5分経過後の自動消化
- `expired` → 期限切れ未使用

### coupon_usage（クーポン使用記録）

会計コンテキストの詳細を残す。`coupon` 本体とは分離して履歴性を確保。

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | UUID | PK | |
| coupon_id | UUID | FK(coupon) NOT NULL | |
| activated_at | TIMESTAMP | NOT NULL | |
| confirmed_at | TIMESTAMP | | 5分以内に確認完了 |
| countdown_completed | BOOLEAN | NOT NULL | 5分経過したか |

UNIQUE`(coupon_id)`

---

## 8. PWA・通知系

### pwa_install（PWAインストール記録）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | UUID | PK | |
| client_id | UUID | FK(client) NOT NULL | |
| platform | VARCHAR(16) | NOT NULL | ios / android / desktop |
| installed_at | TIMESTAMP | NOT NULL | |
| push_token | VARCHAR(512) | | Web Push用 |
| uninstalled_at | TIMESTAMP | | |

**インデックス**：`(client_id, uninstalled_at)` — 現役インストール抽出用

### notification（通知送信履歴）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | UUID | PK | |
| client_id | UUID | FK(client) NOT NULL | |
| store_id | UUID | FK(store) NOT NULL | |
| channel | VARCHAR(16) | NOT NULL | webpush / line / email |
| title | VARCHAR(128) | NOT NULL | |
| body | TEXT | NOT NULL | |
| sent_at | TIMESTAMP | NOT NULL | |
| opened_at | TIMESTAMP | | タップで更新 |
| ai_reason | TEXT | | AIが選定した送信理由のログ |

**インデックス**：`(store_id, sent_at)`, `(client_id, sent_at)`

### notification_quota（月次配信制限）

通知乱発を物理的に防止する。

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| store_id | UUID | FK(store) NOT NULL | PK part |
| year_month | CHAR(7) | NOT NULL | PK part. '2026-05' |
| sent_count | INT | NOT NULL DEFAULT 0 | |
| max_count | INT | NOT NULL DEFAULT 2 | 月2回まで |

PK`(store_id, year_month)`

---

## 9. イベントログ・分析系

### event_log（全イベント記録）— **最重要**

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BIGSERIAL | PK | |
| event_type | VARCHAR(32) | NOT NULL | qr_scanned / survey_started 等 |
| client_id | UUID | FK(client) | NULLABLE（QRスキャン直前等） |
| store_id | UUID | FK(store) NOT NULL | |
| occurred_at | TIMESTAMP | NOT NULL | |
| payload | JSONB | NOT NULL DEFAULT '{}' | イベント固有データ |
| user_agent | VARCHAR(255) | | |
| ip_address | INET | | |
| created_at | TIMESTAMP | NOT NULL | |

**event_type一覧**
- `qr_scanned`
- `survey_started`
- `question_answered`（payload: `{question_id, value}`）
- `survey_phase1_completed`
- `survey_completed`
- `roulette_spun`（payload: `{prize_id, points}`）
- `pwa_install_prompted`
- `pwa_installed`
- `coupon_issued`
- `coupon_activated`
- `coupon_used_start`
- `coupon_used_confirmed`
- `coupon_expired`
- `notification_sent`
- `notification_opened`
- `revisit`（再来店検知）

**インデックス**：`(store_id, occurred_at)`, `(event_type, occurred_at)`, `(client_id, occurred_at)`
**パーティショニング**：月単位（PostgreSQL DECLARATIVE PARTITIONING）。データ販売・古いデータのS3アーカイブに必須。
**絶対に削除しない**。

### daily_metric（日次集計、バッチ生成）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BIGSERIAL | PK | |
| store_id | UUID | FK(store) NOT NULL | |
| metric_date | DATE | NOT NULL | |
| visits | INT | NOT NULL DEFAULT 0 | |
| survey_starts | INT | NOT NULL DEFAULT 0 | |
| survey_completions | INT | NOT NULL DEFAULT 0 | |
| coupons_issued | INT | NOT NULL DEFAULT 0 | |
| coupons_used | INT | NOT NULL DEFAULT 0 | |
| pwa_installs | INT | NOT NULL DEFAULT 0 | |
| avg_satisfaction | DECIMAL(3,2) | | 1.00〜5.00 |
| unique_clients | INT | NOT NULL DEFAULT 0 | DAU |

UNIQUE`(store_id, metric_date)`
**用途**：ダッシュボード表示の高速化、商圏比較、データ販売の集計元。

### monthly_metric（月次集計）

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BIGSERIAL | PK | |
| store_id | UUID | FK(store) NOT NULL | |
| year_month | CHAR(7) | NOT NULL | '2026-05' |
| wau | INT | NOT NULL DEFAULT 0 | 月最終週のWAU |
| mau | INT | NOT NULL DEFAULT 0 | |
| qau | INT | NOT NULL DEFAULT 0 | 直近90日 |
| satisfaction_avg | DECIMAL(3,2) | | |
| repeat_rate | DECIMAL(5,4) | | 0.0000〜1.0000 |
| revenue_jpy | INT | | 課金額 |

UNIQUE`(store_id, year_month)`
**用途**：プラン超過判定、月次レポート、Exit時の財務資料。

---

## 10. リレーション概観

```
owner ──< store ──< store_subscription ──> subscription_plan
                ├──< survey_template ──< question
                ├──< survey_response ──< answer
                ├──< roulette_spin ──> roulette_prize ──> roulette_config
                ├──< coupon ──< coupon_usage
                ├──< notification
                └──< event_log
                
client ──< client_identity
       ├──< client_visit
       ├──< survey_response
       ├──< roulette_spin
       ├──< coupon
       └──< pwa_install
```

---

## 11. 重要な設計判断

### UUID vs SERIAL の使い分け
- **UUID**：外部に露出するもの（store/client/coupon等）。QR URLや名寄せに利用。
- **SERIAL/BIGSERIAL**：内部マスタやログ（event_log/daily_metric）。順序性が欲しい・容量効率優先。

### 論理削除 vs 物理削除
- store/coupon等の業務エンティティ：論理削除（`deleted_at`）
- event_log：**削除一切なし**
- 一時データなし

### 集計テーブルの存在意義
ダッシュボードのたびに event_log を集計するとPostgreSQLが死ぬ。
深夜バッチで daily_metric / monthly_metric を生成し、ダッシュボードはこちらを読む。

### 名寄せ戦略
- 1人のclientが複数チャネル（LINE+メール）登録可能 → `client_identity` を別テーブル化
- 端末買い替え時の引き継ぎは Phase 2 以降の連携で実現
- MVP では UUIDだけ持つ単純な状態

### データ販売対応
- `event_log` を月単位パーティション化
- 個人特定不可な集計は `daily_metric` / `monthly_metric` から提供
- 業態×地域×時系列のグルーピングはこれらの集計テーブルから抽出
- 個別 client_id は API 出力時にハッシュ化

### 海外展開対応
- 全 timestamp は UTC で保存、表示時に locale から timezone 取得
- 通貨は `currency_code` を全金額カラム近傍に持つ（必要に応じて）
- 文言は `_i18n` サフィックスのJSONBに ja/en/... を格納

---

## 12. インデックス戦略まとめ

頻出クエリと推奨インデックス：

| クエリ | インデックス |
|---|---|
| 店舗の本日の回答一覧 | `survey_response(store_id, created_at)` |
| クライアントの保有クーポン | `coupon(client_id, status)` |
| 期限切れクーポンバッチ | `coupon(status, expires_at)` |
| イベントログの店舗別期間集計 | `event_log(store_id, occurred_at)` パーティション込み |
| 商圏分析（近隣店舗検索） | `store(latitude, longitude)` 地理空間index検討 |
| 名寄せ検索 | `client_identity(channel, identifier)` UNIQUE |

---

## 13. マイグレーション戦略

### Phase 0（MVP）で作るテーブル
- owner, store, business_category
- client, client_visit
- survey_template, question, survey_response, answer
- roulette_config, roulette_prize, roulette_spin
- coupon, coupon_usage
- pwa_install
- event_log

### Phase 2 以降で追加
- client_identity（連絡先連携）
- notification, notification_quota
- store_subscription, subscription_plan（課金開始）

### Phase 3 以降で追加
- daily_metric, monthly_metric（バッチ集計）
- store_staff（複数ユーザー対応）

**ポイント**：MVP時点でカラムだけ用意して機能を後回しにできるよう、nullable で持っておく。

---

## 14. セキュリティ・コンプライアンス

- 個人情報を持つテーブル（owner, client_identity）は `created_at` / `updated_at` を必須に
- 30日以上アクセスのない client_identity は削除候補（GDPR等を見据えた設計）
- パスワードは Django auth のハッシュのみ保存
- APIキー・トークンは別テーブル `api_token` で持ち、ハッシュ化（MVPでは未実装）
- イベントログのIPアドレスは個人特定性があるため、データ販売時は除外

---

## 15. 変更履歴

- 2026年5月：初版作成（MVP〜Exit想定の全テーブル網羅）
