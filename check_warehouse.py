#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 向後相容薄殼:驗證器已改名 validate.py(讀 warehouse.yaml 當事實來源)。
# 舊命令 `python3 check_warehouse.py [file]` 仍可用,會直接轉呼叫 validate.py。
import os, runpy
runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'validate.py'),
               run_name='__main__')
