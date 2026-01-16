.PHONY: build up down logs

# BuildKitを有効にして非対話的なビルドを実行
build:
	DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1 docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

restart: down up
