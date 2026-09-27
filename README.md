## Hydrus Network (Client and Server)

The hydrus network client is a file-management application written for internet-fluent media nerds who have large file collections. It browses with tags instead of folders, a little like a booru on your desktop. If they wish, users can easily share tags anonymously through a public server. Everything is free, no ads, and privacy is the first concern. If you have 10,000+ files and cannot find anything, hydrus might help!

Hydrus supports various filetypes for images, video and audio files, image project files, and more. A full list of supported filetypes is [here](https://hydrusnetwork.github.io/hydrus/filetypes.html). It has audio and video playback via an mpv embed or a native Qt player. Some supported filetypes cannot be viewed directly in the client, such as PDF, but it is easy to launch any file with your OS's default program.

I am continually working on the software and try to put out a new release every Wednesday by 8pm EST. Executable releases are available for Windows and Linux, but the program is in python, so you can also just run it straight from the source code in Windows, Linux, or macOS. I am not active here on github, but I welcome feedback of any sort on other channels and will try to get back to any pings every Saturday. 

The client can download files and parse tags and other metadata from simple websites using easily shareable user-made downloaders. It can also be set to 'subscribe' to any gallery search, repeating it every few days to keep up with new results.

The program's emphasis is on your freedom. You control everything, and the program never phones home. In the same way, it is quite an advanced program, and not a beautiful one, so it isn't for everyone. Try it out, see if you like it!

Hydrus is mostly a solo project. **Feel free to fork and do whatever you like with my code, but public pull requests are currently closed.** The [issue tracker here on Github](https://github.com/hydrusnetwork/hydrus/issues) is active and run by volunteer users.

## Start Here!

**[Getting Started Guide](https://hydrusnetwork.github.io/hydrus/introduction.html)**

This help will walk you through installation and teach you the main systems of the program. Hydrus can do a lot, so while you can skim the help, do not skip it. 

The help is also included in every release.

# Links

* [homepage](https://hydrusnetwork.github.io/hydrus/)
* [issue tracker](https://github.com/hydrusnetwork/hydrus/issues)
* [proton](mailto:hydrus_dev@proton.me)
* [gmail](mailto:hydrus.admin@gmail.com)
* [discord](https://discord.gg/wPHPCUZ)
* [tumblr](https://hydrus.tumblr.com/)
* [x](https://x.com/hydrusnetwork)
* [patreon](https://www.patreon.com/hydrus_dev)
* [user-run repository and wiki](https://github.com/CuddleBear92/Hydrus-Presets-and-Scripts)

## Attribution

I use a number of the Silk Icons by Mark James at famfamfam.com.

## Running From Source
See: https://hydrusnetwork.github.io/hydrus/running_from_source.html

```bash
# make sure all 3 show expected output
python --version
python -m pip --version
python -m venv --help
```
```bash
python setup_venv.py 
```

### mpv
Video and audio playback, including the media viewer's audio effects, use mpv. It is not included in this repo.

**Windows:** download [mpv-dev-x86_64-20240818-git-a3baf94.7z](https://sourceforge.net/projects/mpv-player-windows/files/libmpv/mpv-dev-x86_64-20240818-git-a3baf94.7z) (the same build the official Windows release ships), open it, and put `libmpv-2.dll` next to `hydrus_client.py`. Git ignores it there. If you already ran hydrus without it, hydrus switches video, animation, and audio playback over to mpv the next time it starts.

The archive's SHA-256 is `1a7eb75247e06f4acf8e81a0d0bb1e8cacf8fc1a00de402d3cb4f22d19818ce8`. To check it:

```bat
certutil -hashfile mpv-dev-x86_64-20240818-git-a3baf94.7z SHA256
```

**Linux:** install libmpv from your package manager, e.g. `sudo apt install libmpv2`.

### Custom database location
By default the client keeps its database in the `db` folder next to `hydrus_client.py`. To keep it somewhere else on Windows, pass the folder with `-d` in the launch script:

1. Copy `hydrus_client.bat` to `hydrus_client-user.bat`. Git ignores that filename, so a `git pull` won't overwrite your changes.
2. In the copy, find this line:

   ```bat
   start "" "pythonw" hydrus_client.pyw
   ```

   and add `-d` with your folder:

   ```bat
   start "" "pythonw" hydrus_client.pyw -d="E:\hydrus"
   ```

3. Start hydrus with `hydrus_client-user.bat` from now on.

A few things to know:

- If the folder doesn't exist, hydrus creates it and starts a new, empty database there. To keep your existing database, close the client and move everything in the old `db` folder into the new one before you launch.
- A relative path such as `-d="..\hydrus_db"` is resolved from the hydrus install folder.
- Don't end the path with a backslash (`"E:\hydrus\"`), because Windows then reads `\"` as a literal quote and hydrus gets the wrong path.
- To launch with the console open for debugging, add the same flag to the commented-out line instead: `python hydrus_client.py -d="E:\hydrus"`.
