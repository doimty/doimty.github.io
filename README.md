# Doimty Repo

GitHub Pages hosted jailbreak APT repo.

Source URL:

```text
https://doimty.github.io/
```

## Add a deb

Put `.deb` files into `debs/`, then run:

```bash
./scripts/update-repo.sh
```

Commit and push generated `Packages*` and `Release` files.

## 源码发布边界

此仓库用于公开软件源文件，不发布私有插件仓库的源码、源码归档或私有构建入口。安装包与私有源码分开维护。

`GitHub Pages` 仅上传 `scripts/prepare-pages.py` 核验后生成的 `_site/`，不上传整个工作树。公开开源归档必须登记精确 SHA-256，且来源仓库实时可匿名核验为公开；未知归档、摘要变化、私有或无法核验的来源都会阻止部署。保留既有开源项目的许可声明。

发布前检查：

```sh
python3 scripts/test-prepare-pages.py
python3 scripts/prepare-pages.py --output _site
```
