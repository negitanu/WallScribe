.PHONY: build up down logs test format lint type-check install-dev rebuild

# BuildKitを有効にして非対話的なビルドを実行
build:
	DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1 docker compose build

# キャッシュなしで再ビルド（api/utilsディレクトリ追加後の再ビルド用）
rebuild:
	DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1 docker compose build --no-cache

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

restart: down up

# 開発環境のセットアップ
install-dev:
	pip install -r requirements-dev.txt
	pre-commit install

# テスト実行
test:
	pytest -v --cov=. --cov-report=html --cov-report=term-missing

test-fast:
	pytest -v --no-cov

# コードフォーマット
format:
	black .
	isort .

format-check:
	black --check .
	isort --check-only .

# リンター
lint:
	flake8 . --max-line-length=100 --extend-ignore=E203,W503

# 型チェック
type-check:
	mypy . --ignore-missing-imports --no-strict-optional

# コード品質チェック（全て実行）
check: format-check lint type-check test

# セキュリティチェック
security-check:
	safety check
	pip-audit

# クリーンアップ
clean:
	find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} + 2>/dev/null || true
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf coverage.xml
	rm -rf .mypy_cache
	rm -rf .ruff_cache
