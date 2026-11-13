import sys
import os
import time
sys.path.append(os.path.dirname(os.path.abspath(__name__)))
from src.precog_esgf_intake.scripts.intake_UtilFuncs import print_precog_header, print_precog_footer

print('\n')
msg ='Behold! A nice header is about to appear . . .'
for ith, word in enumerate(msg.split(" ")):
    print(word, end=" ", flush=True)
    time.sleep(.5)

print('\n'*2)

print_precog_header()

msg ="Hooray it seems you configured things correctly. Hellen says 'hi' from the depths."

for ith, word in enumerate(msg.split(" ")):
    print(word, end=" ", flush=True)
    time.sleep(.5)

print('\n'*2)

print_precog_footer()