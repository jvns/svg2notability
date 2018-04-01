### pdf (or SVG) to notability

This is a very hacky Python script that converts from PDF format to the proprietary Notability
format (Notability is an iOS note-taking app), so that you can **edit** (not just annotate) the
resulting files in Notability.

This was written for my own personal use (converting handwritten documents exported from Squid on
Android) and may or may not work for anyone else. Sharing this because I spent 5ish hours writing
it, in the hopes that it may be useful to someone else.

You can also easily modify the script to convert from SVG to notability (just take out the
pdf-to-svg conversion step).

### requirements

* plistutil on Linux
* Inkscape

### usage

```
# creates my-file.note in current directory
python pdf2notability.py my-file.pdf
```

### limitations

* only handles an extremely limited subset of SVGs. your average SVG will probably not work
* can't create notes with multiple pages
* gets your page sizes wrong
* doesn't handle squares
* probably lots more things I'm leaving out
