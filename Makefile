SHELL := /bin/zsh

UV ?= $(HOME)/.local/bin/uv
PYTHON_VERSION ?= 3.13.12
VENV_DIR ?= .venv
PYTHON := $(VENV_DIR)/bin/python
PID_DIR := .pids
LOG_DIR := logs

DEST_SERVER := tool_servers.destination_tools.main
TRANSPORT_SERVER := tool_servers.transport_tools.main
PRICING_SERVER := tool_servers.pricing_db_tools.main

DEST_PID := $(PID_DIR)/destination-tools.pid
TRANSPORT_PID := $(PID_DIR)/transport-tools.pid
PRICING_PID := $(PID_DIR)/pricing-db-tools.pid

.PHONY: venv recreate-venv install install-agents verify-agents bootstrap seed-db start-tools stop check-ports sanity verify-tools

venv:
	@if [ -x "$(PYTHON)" ] && "$(PYTHON)" -V | grep -q "$(PYTHON_VERSION)"; then \
		echo "Virtual environment $(VENV_DIR) already uses Python $(PYTHON_VERSION)."; \
	elif [ -d "$(VENV_DIR)" ]; then \
		echo "Recreating $(VENV_DIR) with Python $(PYTHON_VERSION)..."; \
		$(UV) venv --python $(PYTHON_VERSION) --clear $(VENV_DIR); \
	else \
		$(UV) venv --python $(PYTHON_VERSION) $(VENV_DIR); \
	fi

recreate-venv:
	$(UV) venv --python $(PYTHON_VERSION) --clear $(VENV_DIR)

install: venv
	$(UV) pip install --python $(PYTHON) -r requirements.txt

install-agents: venv
	$(UV) pip install --python $(PYTHON) -r requirements.agents.txt

verify-agents: venv
	$(PYTHON) -V
	$(PYTHON) -c "import crewai; print(crewai.__version__)"
	$(PYTHON) -c "import a2a; print('a2a ok')"
	$(UV) pip check --python $(PYTHON)

bootstrap: install seed-db

seed-db:
	$(PYTHON) -m data.seed_db

check-ports:
	@echo "Checking ports 8001, 8002, 8003..."
	@for p in 8001 8002 8003; do \
		if lsof -iTCP:$$p -sTCP:LISTEN >/dev/null 2>&1; then \
			echo "Port $$p is already in use"; exit 1; \
		else \
			echo "Port $$p is free"; \
		fi; \
	done

start-tools: install seed-db check-ports
	@mkdir -p $(PID_DIR) $(LOG_DIR)
	@nohup $(PYTHON) -m $(DEST_SERVER) > $(LOG_DIR)/destination-tools.log 2>&1 & echo $$! > $(DEST_PID)
	@nohup $(PYTHON) -m $(TRANSPORT_SERVER) > $(LOG_DIR)/transport-tools.log 2>&1 & echo $$! > $(TRANSPORT_PID)
	@nohup $(PYTHON) -m $(PRICING_SERVER) > $(LOG_DIR)/pricing-db-tools.log 2>&1 & echo $$! > $(PRICING_PID)
	@echo "Started destination-tools (PID $$(cat $(DEST_PID))) on :8001"
	@echo "Started transport-tools (PID $$(cat $(TRANSPORT_PID))) on :8002"
	@echo "Started pricing-db-tools (PID $$(cat $(PRICING_PID))) on :8003"

stop:
	@for pid_file in $(DEST_PID) $(TRANSPORT_PID) $(PRICING_PID); do \
		if [ -f $$pid_file ]; then \
			pid=$$(cat $$pid_file); \
			if kill -0 $$pid >/dev/null 2>&1; then \
				kill $$pid && echo "Stopped PID $$pid"; \
			fi; \
			rm -f $$pid_file; \
		fi; \
	done

sanity:
	$(PYTHON) -m scripts.sanity_calls

verify-tools:
	@echo "Verifying /tools endpoints..."
	@curl -fsS http://localhost:8001/tools | grep -q "get_destination_info"
	@curl -fsS http://localhost:8001/tools | grep -q "get_local_events"
	@curl -fsS http://localhost:8002/tools | grep -q "search_flights"
	@curl -fsS http://localhost:8002/tools | grep -q "search_hotels"
	@curl -fsS http://localhost:8002/tools | grep -q "calculate_total_cost"
	@curl -fsS http://localhost:8003/tools | grep -q "lookup_avg_price"
	@curl -fsS http://localhost:8003/tools | grep -q "get_budget_tiers"
	@echo "All /tools endpoint checks passed."
