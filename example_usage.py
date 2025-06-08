#!/usr/bin/env python3
"""PDF解析機能の使用例"""

import os
import logging
from dotenv import load_dotenv
import google.generativeai as genai

from pdf_podcast.pdf_parser import PDFParser

# ログ設定
logging.basicConfig(level=logging.INFO)

# 環境変数の読み込み
load_dotenv()

# Gemini APIキーの設定
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
else:
    print("警告: GOOGLE_API_KEYが設定されていません。.envファイルを確認してください。")

def main():
    # テスト用PDFファイル
    pdf_path = "test/test.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"エラー: {pdf_path} が見つかりません")
        return
    
    try:
        # PDFパーサーの初期化
        parser = PDFParser(pdf_path)
        
        # 章の抽出
        print("章を抽出中...")
        chapters = parser.extract_chapters()
        
        # 結果の表示
        print(f"\n検出された章数: {len(chapters)}")
        for i, chapter in enumerate(chapters, 1):
            print(f"\n--- 章 {i} ---")
            print(f"タイトル: {chapter.title}")
            print(f"ページ: {chapter.start_page} - {chapter.end_page}")
            print(f"テキスト冒頭: {chapter.text[:200]}...")
            
    except Exception as e:
        print(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    main()