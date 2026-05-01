ANVIL_USER         := x-kozler
ANVIL_HOST         := anvil.rcac.purdue.edu
ANVIL_PATH         := /anvil/projects/x-cis251377/x-kozler/repositories/clinical-generation-and-evaluation/

ACES_HOST          := aces
ACES_PATH          := /scratch/group/p.cis251377.000/u.ko341547/repositories/clinical-generation-and-evaluation/

STAMPEDE3_HOST     := stampede3
STAMPEDE3_PATH     := /work2/11527/kbozler/stampede3/repositories/clinical-generation-and-evaluation/

LOCAL_PATH         := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
DOTFILES_ANVIL     := $(LOCAL_PATH)dotfiles/anvil
DOTFILES_ACES      := $(LOCAL_PATH)dotfiles/aces
DOTFILES_STAMPEDE3 := $(LOCAL_PATH)dotfiles/stampede3

PUSH_EXCLUDES      := --exclude='.claude/' --exclude='outputs/' --exclude='logs/' --exclude='dotfiles/' --exclude='__pycache__/' --exclude='.DS_Store' --exclude='slurm/' --exclude='docs/'

.PHONY: push-anvil pull-anvil push-aces pull-aces push-stampede3 pull-stampede3 push-dotfiles-anvil push-dotfiles-aces push-dotfiles-stampede3 install-aces-keys

push-anvil:
	ssh $(ANVIL_USER)@$(ANVIL_HOST) 'mkdir -p $(ANVIL_PATH)slurm $(ANVIL_PATH)docs $(ANVIL_PATH)outputs $(ANVIL_PATH)logs'
	rsync -avz --delete --progress $(PUSH_EXCLUDES) $(LOCAL_PATH) $(ANVIL_USER)@$(ANVIL_HOST):$(ANVIL_PATH)
	rsync -avz --delete --progress $(LOCAL_PATH)slurm/anvil/ $(ANVIL_USER)@$(ANVIL_HOST):$(ANVIL_PATH)slurm/
	rsync -avz --delete --progress $(LOCAL_PATH)docs/anvil.md $(ANVIL_USER)@$(ANVIL_HOST):$(ANVIL_PATH)docs/

pull-anvil:
	mkdir -p $(LOCAL_PATH)outputs/anvil $(LOCAL_PATH)logs/anvil
	ssh $(ANVIL_USER)@$(ANVIL_HOST) 'mkdir -p $(ANVIL_PATH)outputs $(ANVIL_PATH)logs'
	rsync -avz --progress $(ANVIL_USER)@$(ANVIL_HOST):$(ANVIL_PATH)outputs/ $(LOCAL_PATH)outputs/anvil/
	rsync -avz --progress $(ANVIL_USER)@$(ANVIL_HOST):$(ANVIL_PATH)logs/ $(LOCAL_PATH)logs/anvil/

push-aces:
	ssh $(ACES_HOST) 'mkdir -p $(ACES_PATH)slurm $(ACES_PATH)docs $(ACES_PATH)outputs $(ACES_PATH)logs'
	rsync -avz --delete --progress $(PUSH_EXCLUDES) $(LOCAL_PATH) $(ACES_HOST):$(ACES_PATH)
	rsync -avz --delete --progress $(LOCAL_PATH)slurm/aces/ $(ACES_HOST):$(ACES_PATH)slurm/
	rsync -avz --delete --progress $(LOCAL_PATH)docs/aces.md $(ACES_HOST):$(ACES_PATH)docs/

pull-aces:
	mkdir -p $(LOCAL_PATH)outputs/aces $(LOCAL_PATH)logs/aces
	ssh $(ACES_HOST) 'mkdir -p $(ACES_PATH)outputs $(ACES_PATH)logs'
	rsync -avz --progress $(ACES_HOST):$(ACES_PATH)outputs/ $(LOCAL_PATH)outputs/aces/
	rsync -avz --progress $(ACES_HOST):$(ACES_PATH)logs/ $(LOCAL_PATH)logs/aces/

push-stampede3:
	ssh $(STAMPEDE3_HOST) 'mkdir -p $(STAMPEDE3_PATH)slurm $(STAMPEDE3_PATH)docs $(STAMPEDE3_PATH)outputs $(STAMPEDE3_PATH)logs'
	rsync -avz --delete --progress $(PUSH_EXCLUDES) $(LOCAL_PATH) $(STAMPEDE3_HOST):$(STAMPEDE3_PATH)
	rsync -avz --delete --progress $(LOCAL_PATH)slurm/stampede3/ $(STAMPEDE3_HOST):$(STAMPEDE3_PATH)slurm/
	rsync -avz --delete --progress $(LOCAL_PATH)docs/stampede3.md $(STAMPEDE3_HOST):$(STAMPEDE3_PATH)docs/

pull-stampede3:
	mkdir -p $(LOCAL_PATH)outputs/stampede3 $(LOCAL_PATH)logs/stampede3
	ssh $(STAMPEDE3_HOST) 'mkdir -p $(STAMPEDE3_PATH)outputs $(STAMPEDE3_PATH)logs'
	rsync -avz --progress $(STAMPEDE3_HOST):$(STAMPEDE3_PATH)outputs/ $(LOCAL_PATH)outputs/stampede3/
	rsync -avz --progress $(STAMPEDE3_HOST):$(STAMPEDE3_PATH)logs/ $(LOCAL_PATH)logs/stampede3/

push-dotfiles-anvil:
	rsync -avz --progress $(DOTFILES_ANVIL)/.bashrc $(ANVIL_USER)@$(ANVIL_HOST):~/.bashrc
	rsync -avz --progress $(DOTFILES_ANVIL)/.bash_env $(ANVIL_USER)@$(ANVIL_HOST):~/.bash_env

push-dotfiles-aces:
	rsync -avz --progress $(DOTFILES_ACES)/.bashrc $(ACES_HOST):~/.bashrc
	rsync -avz --progress $(DOTFILES_ACES)/.bash_env $(ACES_HOST):~/.bash_env

push-dotfiles-stampede3:
	rsync -avz --progress $(DOTFILES_STAMPEDE3)/.bashrc $(STAMPEDE3_HOST):~/.bashrc
	rsync -avz --progress $(DOTFILES_STAMPEDE3)/.bash_env $(STAMPEDE3_HOST):~/.bash_env

install-aces-keys:
	cp "$(HOME)/Downloads/aces keys/id_aces_tamu" $(HOME)/.ssh/id_aces_tamu
	cp "$(HOME)/Downloads/aces keys/id_aces_tamu-cert.pub" $(HOME)/.ssh/id_aces_tamu-cert.pub
	chmod 600 $(HOME)/.ssh/id_aces_tamu
	chmod 644 $(HOME)/.ssh/id_aces_tamu-cert.pub
	@echo "ACES keys installed to $(HOME)/.ssh"
