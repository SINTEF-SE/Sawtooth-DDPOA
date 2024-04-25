docker compose -p latest -f fault_tolerance/workload.yml down --remove-orphans --volumes
docker compose -p latest-alpha -f fault_tolerance/node.yml down --remove-orphans --volumes
docker compose -p latest-beta -f fault_tolerance/node.yml down --remove-orphans --volumes
docker compose -p latest-gamma -f fault_tolerance/node.yml down --remove-orphans --volumes
docker compose -p latest-delta -f fault_tolerance/node.yml down --remove-orphans --volumes
GENESIS=1 docker compose -p latest-epsilon -f fault_tolerance/node.yml down --remove-orphans --volumes
docker compose -p latest -f fault_tolerance/admin.yml down --remove-orphans --volumes