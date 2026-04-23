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
ITINERARY_A2A_SERVER := a2a_servers.itinerary_server
SCOUT_A2A_SERVER := a2a_servers.scout_server
BUDGET_A2A_SERVER := a2a_servers.budget_server

DEST_PID := $(PID_DIR)/destination-tools.pid
TRANSPORT_PID := $(PID_DIR)/transport-tools.pid
PRICING_PID := $(PID_DIR)/pricing-db-tools.pid
ITINERARY_A2A_PID := $(PID_DIR)/itinerary-a2a.pid
SCOUT_A2A_PID := $(PID_DIR)/scout-a2a.pid
BUDGET_A2A_PID := $(PID_DIR)/budget-a2a.pid

.PHONY: venv recreate-venv install install-agents verify-agents bootstrap seed-db start-tools start-agents stop check-ports check-agent-ports sanity verify-tools verify-agent-cards

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

check-agent-ports:
	@echo "Checking ports 9001, 9002, 9003..."
	@for p in 9001 9002 9003; do \
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

start-agents: install-agents check-agent-ports
	@mkdir -p $(PID_DIR) $(LOG_DIR)
	@nohup $(PYTHON) -m $(ITINERARY_A2A_SERVER) > $(LOG_DIR)/itinerary-a2a.log 2>&1 & echo $$! > $(ITINERARY_A2A_PID)
	@nohup $(PYTHON) -m $(SCOUT_A2A_SERVER) > $(LOG_DIR)/scout-a2a.log 2>&1 & echo $$! > $(SCOUT_A2A_PID)
	@nohup $(PYTHON) -m $(BUDGET_A2A_SERVER) > $(LOG_DIR)/budget-a2a.log 2>&1 & echo $$! > $(BUDGET_A2A_PID)
	@echo "Started itinerary-a2a (PID $$(cat $(ITINERARY_A2A_PID))) on :9001"
	@echo "Started scout-a2a (PID $$(cat $(SCOUT_A2A_PID))) on :9002"
	@echo "Started budget-a2a (PID $$(cat $(BUDGET_A2A_PID))) on :9003"

stop:
	@for pid_file in $(DEST_PID) $(TRANSPORT_PID) $(PRICING_PID) $(ITINERARY_A2A_PID) $(SCOUT_A2A_PID) $(BUDGET_A2A_PID); do \
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

verify-agent-cards:
	@echo "Verifying Agent Card endpoints..."
	@curl -fsS http://localhost:9001/.well-known/agent-card.json | grep -q "itinerary_specialist"
	@curl -fsS http://localhost:9002/.well-known/agent-card.json | grep -q "flight_hotel_specialist"
	@curl -fsS http://localhost:9003/.well-known/agent-card.json | grep -q "budget_specialist"
	@echo "All Agent Card checks passed."
