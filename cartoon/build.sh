set -e
F=30; FONT=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
# name|image|start|end|zoom expr|x expr|y expr|caption
S=(
"c0|s5_boy.png|0|3.5|1.05+0.03*sin(on/6)|iw/2-(iw/zoom/2)|ih/2-(ih/zoom/2)+20*sin(on/5)|Привет! Я Капа"
"c1|s0_full.png|3.5|4.9|1.0+0.0025*on|iw/2-(iw/zoom/2)|ih/2-(ih/zoom/2)|А что если?"
"c2|s1_meteor.png|4.9|8.2|1.1+0.002*on|iw/2-(iw/zoom/2)+12*sin(on*2.1)|ih/2-(ih/zoom/2)+12*cos(on*1.7)|...астероид полетит к Земле?"
"c3|s2_dino.png|8.2|11.7|1.25-0.0015*on|iw/2-(iw/zoom/2)+lt(on\,15)*10*sin(on*3)|ih/2-(ih/zoom/2)|...динозавры вернутся?"
"c4|s3_city.png|11.7|15.5|1.15|(iw-iw/zoom)*on/114|ih/2-(ih/zoom/2)|...город будущего?"
"c5|s4_hourglass.png|15.5|18.6|1.0+0.004*on|iw/2-(iw/zoom/2)|ih/2-(ih/zoom/2)|...время остановится?"
"c6|s5_boy.png|18.6|21.2|1.25-0.002*on|iw/2-(iw/zoom/2)|ih/2-(ih/zoom/2)|Ответы — на моём канале!"
"c7|s0_full.png|21.2|25.0|1.12-0.001*on|iw/2-(iw/zoom/2)|ih/2-(ih/zoom/2)|ПОДПИСЫВАЙСЯ!"
)
> list.txt
for row in "${S[@]}"; do IFS='|' read n img a b z x y cap <<<"$row"
 d=$(python3 -c "print(round($b-$a,3))"); N=$(python3 -c "print(round(($b-$a)*$F))")
 printf '%s' "$cap" > $n.txt
 ffmpeg -y -loglevel error -i $img -filter_complex "scale=3840:2160,zoompan=z='$z':x='$x':y='$y':d=$N:s=1920x1080:fps=$F,setsar=1,
 drawtext=fontfile=$FONT:textfile=$n.txt:fontsize='if(lt(t,0.25),96*t/0.25,96)':fontcolor=white:borderw=8:bordercolor=black:shadowx=6:shadowy=6:shadowcolor=0xD32F2F:x=(w-text_w)/2:y=h-200,
 fade=t=in:st=0:d=0.2,format=yuv420p" -frames:v $N -c:v libx264 -crf 19 -preset medium -r $F $n.mp4
 echo "file '$n.mp4'" >> list.txt; done
ffmpeg -y -loglevel error -f concat -safe 0 -i list.txt -c copy video_only.mp4
ffmpeg -y -loglevel error -i video_only.mp4 -i voice.mp3 -filter_complex "[1:a]adelay=500|500,apad,volume=1.1[a]" -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart kapa_cartoon.mp4
ffprobe -v error -show_entries format=duration -of default=nw=1 kapa_cartoon.mp4
