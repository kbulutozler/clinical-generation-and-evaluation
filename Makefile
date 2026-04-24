ANVIL_USER     := x-kozler
ANVIL_HOST     := anvil.rcac.purdue.edu
ANVIL_PATH     := /anvil/projects/x-cis251377/x-kozler/repositories/clinical-generation-and-evaluation/

ACES_HOST      := aces
ACES_PATH      := /scratch/group/p.cis251377.000/u.ko341547/repositories/clinical-generation-and-evaluation/

LOCAL_PATH     := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
DOTFILES_ACES  := $(LOCAL_PATH)dotfiles/aces

PUSH_EXCLUDES  := --exclude='.claude/' --exclude='outputs/' --exclude='logs/' --exclude='sync/install_aces_keys.sh'

.PHONY: push-anvil pull-anvil push-aces pull-aces push-dotfiles-aces install-aces-keys

push-anvil:
	rsync -avz --delete --progress $(PUSH_EXCLUDES) $(LOCAL_PATH) $(ANVIL_USER)@$(ANVIL_HOST):$(ANVIL_PATH)

pull-anvil:
	rsync -avz --progress $(ANVIL_USER)@$(ANVIL_HOST):$(ANVIL_PATH)outputs/ $(LOCAL_PATH)outputs/
	rsync -avz --progress $(ANVIL_USER)@$(ANVIL_HOST):$(ANVIL_PATH)logs/ $(LOCAL_PATH)logs/

push-aces:
	rsync -avz --delete --progress $(PUSH_EXCLUDES) $(LOCAL_PATH) $(ACES_HOST):$(ACES_PATH)

pull-aces:
	rsync -avz --progress $(ACES_HOST):$(ACES_PATH)outputs/ $(LOCAL_PATH)outputs/
	rsync -avz --progress $(ACES_HOST):$(ACES_PATH)logs/ $(LOCAL_PATH)logs/
	rsync -avz --progress $(ACES_HOST):$(ACES_PATH)prompts/ $(LOCAL_PATH)prompts/

push-dotfiles-aces:
	rsync -avz --progress $(DOTFILES_ACES)/.bashrc $(ACES_HOST):~/.bashrc
	rsync -avz --progress $(DOTFILES_ACES)/.bash_env $(ACES_HOST):~/.bash_env

install-aces-keys:
	cp "$(HOME)/Downloads/aces keys/id_aces_tamu" $(HOME)/.ssh/id_aces_tamu
	cp "$(HOME)/Downloads/aces keys/id_aces_tamu-cert.pub" $(HOME)/.ssh/id_aces_tamu-cert.pub
	chmod 600 $(HOME)/.ssh/id_aces_tamu
	chmod 644 $(HOME)/.ssh/id_aces_tamu-cert.pub
	@echo "ACES keys installed to $(HOME)/.ssh"
