/**
 * Copyright 2024 Øivind Loe
 * SPDX-License-Identifier: Apache-2.0
 * Licensed under the Apache License, Version 2.0 (the "License");
 * See LICENSE file or http://www.apache.org/licenses/LICENSE-2.0 for details.
 * ~
 **/
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    include: ['rich_content.test.js', 'activity_tree.test.js', 'activity_tree.render.test.js'],
    // Node 25+ defines a global `localStorage` that is undefined unless --localstorage-file
    // is given, and it shadows the one jsdom installs. Turn Node's Web Storage off so jsdom's
    // wins. Must be a config option; `--execArgv` on the vitest CLI is ignored.
    execArgv: ['--no-experimental-webstorage'],
  },
});
