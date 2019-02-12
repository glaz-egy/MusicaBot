# これはなんですか？
MusicaBotはPlatinaBotの機能縮小版です。

MusicBotとして機能のみを残し、最適化されています。
# 使い方
使い方は至って簡単。

まず、[Python公式サイト](https://www.python.org/)より、Python3をダウンロードしてインストールしましょう。

次に[FFmpeg公式サイト](https://www.ffmpeg.org/)からFFmpegをダウンロードしてインストールします。

最後に、init.batを管理者権限で実行してもらえれば終了です。

後は、[Botを登録](https://discordapp.com/developers/applications/)して、config.iniを編集したら、使いたいときにstart.batを実行して、Botを起動しましょう。

# config.iniについて
config.iniは
```
[BOTDATA]
token = None
cmdprefix = ;
lang = JP

[ADMINDATA]
botowner = None
```
のようになっています。
tokenはBotのトークン、cmdprefixはコマンドを入力するときに先頭に入れる記号、langは使用言語。

botownerはBot管理者のIDを入れましょう。