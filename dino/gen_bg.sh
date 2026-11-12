STYLE="vibrant cartoon digital illustration, bright saturated colors, kids animated movie style, highly detailed, cinematic, no text, no people"
declare -A P=(
[b1]="cozy kid bedroom with dinosaur posters, dinosaur toys and books on shelves, warm daylight"
[b2]="magical glowing swirling time portal vortex, blue and orange energy, sparks"
[b3]="prehistoric jungle with giant ferns, smoking volcano in the background, misty morning"
[b4]="herd of huge long-necked brachiosaurus dinosaurs drinking at a prehistoric lake"
[b5]="family of triceratops dinosaurs grazing on a sunny prehistoric meadow with flowers"
[b6]="flock of pterodactyls flying over tall rocky cliffs at golden sunset"
[b7]="huge angry tyrannosaurus rex roaring and running toward the viewer in a dense jungle, dramatic"
[b8]="giant fiery asteroid falling from the sky over a prehistoric landscape, dinosaurs looking up, dramatic red sky"
)
for k in b1 b2 b3 b4 b5 b6 b7 b8; do
  [ -s $k.jpg ] && file $k.jpg | grep -q JPEG && continue
  q=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "${P[$k]}, $STYLE")
  for t in 1 2 3 4 5 6; do
    c=$(curl -sS -L -m 180 -o $k.jpg -w '%{http_code}' "https://image.pollinations.ai/prompt/$q?width=1344&height=768&nologo=true&seed=7")
    echo "$k try$t HTTP $c"; [ "$c" = 200 ] && break; sleep 30; done
  sleep 20
done
