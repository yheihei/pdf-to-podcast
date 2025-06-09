# PRD: Scripts-to-Audio機能

## 背景
- PDFからスクリプト生成は完了しているが、音声生成が途中で止まっている状況
- レート制限（429エラー）により音声生成が中断されるケースが多発
- 音声未生成のスクリプトファイルに対してのみ音声生成を実行したい

## 問題
現在のシステムでは、音声生成が途中で止まった場合：
- 最初から全処理を実行する必要がある
- PDFの解析とスクリプト生成を再度実行してしまう
- 既存の音声ファイルも再生成しようとする

## 要件

### 基本機能
新しいコマンドラインオプション`--scripts-to-audio`を追加

```bash
python -m pdf_podcast --scripts-to-audio <scripts_directory_path>
```

### 処理仕様
1. **PDFの解析をスキップ**
2. **スクリプト生成をスキップ**
3. **既存のスクリプトファイルから音声を生成**
4. **既存の音声ファイルは必ずスキップ**（強制的にskip_existing=True）

### ディレクトリ指定
1. スクリプトディレクトリのパスを直接指定
2. 相対パス・絶対パスの両方をサポート
   - 例：`scripts/software_architecture-13-379_2`
   - 例：`./output/scripts/software_architecture-13-379_2`

### 音声未生成ファイルの検出
```
指定されたscriptsディレクトリ/*.txt と 対応するaudioディレクトリ/*.mp3 を比較
音声ファイルが存在しないスクリプトのみを処理対象とする

例：
scripts/software_architecture-13-379_2/*.txt
audio/software_architecture-13-379_2/*.mp3
```

## 実装詳細

### 1. コマンドライン引数の追加
```python
parser.add_argument('--scripts-to-audio', type=str, metavar='SCRIPTS_DIR',
                    help='指定されたスクリプトディレクトリから音声のみを生成（PDF解析とスクリプト生成をスキップ）')
```

### 2. ディレクトリ検証関数
```python
def validate_scripts_directory(scripts_dir_path: str) -> Path:
    """指定されたスクリプトディレクトリの存在を確認"""
    scripts_dir = Path(scripts_dir_path)
    if not scripts_dir.exists():
        raise ValueError(f"スクリプトディレクトリが見つかりません: {scripts_dir_path}")
    if not scripts_dir.is_dir():
        raise ValueError(f"指定されたパスはディレクトリではありません: {scripts_dir_path}")
    return scripts_dir
```

### 3. 音声未生成ファイル検出
```python
def get_missing_audio_files(scripts_dir: Path, audio_dir: Path) -> List[Path]:
    """音声が未生成のスクリプトファイルを取得"""
    script_files = {f.stem: f for f in scripts_dir.glob("*.txt")}
    audio_files = {f.stem for f in audio_dir.glob("*.mp3")}
    
    missing = []
    for stem, script_path in script_files.items():
        if stem not in audio_files:
            missing.append(script_path)
    
    return missing
```

### 4. 処理フローの変更
`--scripts-to-audio`モード時：
1. 指定されたスクリプトディレクトリの存在を確認
2. 対応する音声ディレクトリを特定（scriptsをaudioに置換）
3. 音声未生成のスクリプトファイルを検出
4. それらのスクリプトに対してのみ音声生成を実行

## 使用例

### 通常の処理
```bash
# 新規でPDFから全処理
python -m pdf_podcast --input test.pdf --output-dir ./output
```

### Scripts-to-Audio機能
```bash
# 既存スクリプトから音声未生成分のみ処理
python -m pdf_podcast --scripts-to-audio ./output/scripts/software_architecture-13-379_2

# 相対パスでも指定可能
python -m pdf_podcast --scripts-to-audio scripts/software_architecture-13-379_2
```

### 進捗表示例
```
Scripts-to-Audio モード
スクリプトディレクトリ: ./output/scripts/software_architecture-13-379_2
音声ディレクトリ: ./output/audio/software_architecture-13-379_2
- スクリプト総数: 179
- 生成済み音声: 90
- 未生成音声: 89
- 処理対象: 89ファイル

音声生成中... [■■■□□□□□□□] 30/89 (33.7%)
```

## 成功基準
1. 既存のスクリプトから音声未生成分のみを正確に検出できる
2. 既存の音声ファイルを確実にスキップできる
3. レート制限で中断された処理を効率的に再開できる
4. PDFの解析とスクリプト生成をスキップして高速処理できる

## エラーハンドリング強化

### 429エラー時の処理停止と再開ガイダンス
TTS処理中に429エラー（レート制限）が発生した場合：

1. **処理を即座に停止**
2. **進捗状況を表示**
3. **再開コマンドを提示**

#### エラーメッセージ例
```
❌ レート制限エラー (429) が発生しました

処理状況:
- 処理済み音声: 45/179 ファイル (25.1%)
- 残り: 134 ファイル

時間をおいて以下のコマンドで処理を再開してください:
python -m pdf_podcast --scripts-to-audio ./output/scripts/software_architecture-13-379_2

推奨待機時間: 2-5分
```

### API制限の詳細
**Gemini 2.5 Flash Preview TTS (Free Tier):**
- RPM: 3 requests per minute（20秒に1リクエスト）
- RPD: 15 requests per day
- TPM: 10,000 tokens per minute

### 実装詳細
```python
def handle_rate_limit_error(scripts_dir: str, processed: int, total: int):
    """429エラー時の処理停止とガイダンス表示"""
    print(f"❌ レート制限エラー (429) が発生しました\n")
    print(f"API制限: Free Tierは1分間に3リクエストまで")
    print(f"処理状況:")
    print(f"- 処理済み: {processed}/{total} ファイル ({processed/total*100:.1f}%)")
    print(f"- 残り: {total-processed} ファイル\n")
    print(f"時間をおいて以下のコマンドで処理を再開してください:")
    print(f"python -m pdf_podcast --scripts-to-audio {scripts_dir}\n")
    print(f"推奨待機時間: 2-5分")
    print(f"※ 既存の音声ファイルは自動でスキップされます")
    sys.exit(1)
```

## 非機能要件
- 処理時間：従来の1/3以下（PDF解析・スクリプト生成をスキップするため）
- ファイル安全性：既存ファイルの上書きを防ぐ
- エラーハンドリング：適切なディレクトリが見つからない場合の明確なエラーメッセージ
- レート制限対応：429エラー時の適切な処理停止と再開ガイダンス

## テスト項目
1. `--scripts-to-audio`でPDF解析がスキップされることを確認
2. 音声未生成ファイルの検出が正確であることを確認
3. 既存音声ファイルがスキップされることを確認
4. レート制限エラーからの復旧が正常に動作することを確認
5. 存在しないディレクトリを指定した場合のエラーハンドリングを確認
6. 相対パス・絶対パスの両方で正常に動作することを確認
7. 429エラー時に適切なエラーメッセージと再開コマンドが表示されることを確認
8. 429エラー後の再開処理で既存ファイルが正しくスキップされることを確認