# Ichi for Just Natsuki

A fan-made card game submod for [Just Natsuki](https://github.com/Just-Natsuki-Team/NatsukiModDev), built in Ren'Py 6.99 and inspired by UNO.

<p align="center">
  <img src="media/jn-ichi-preview1.gif" alt="Ichi gameplay preview 1" width="100%">
</p>

> [!WARNING]
> **This is an unofficial fan-made submod for Just Natsuki. It is not affiliated with the Just Natsuki team.**  
> The developers are **not responsible for troubleshooting this submod** or problems caused by installing it.  
>
> > Before installing, **please back up your persistent data:** [How to back up your JN persistent file](https://github.com/Just-Natsuki-Team/NatsukiModDev/wiki/04:-FAQ#can-i-back-up-my-save-data--how-do-i-find-my-persistent)

*Seriously please for the love of god it takes like zero effort, just back up your persistent file (it is a really good habit)*

---

## What is this?

**Ichi** adds a new card game to Just Natsuki, complete with:

- full playable matches against Natsuki
- unlockable gameplay modes and house rules
- in-character introduction and rules explanations
- witty tsundere banter action throughout play
- rematches, forfeits, win/loss scenes, and spree reactions
- three affinity tiers factored into dialogue and tone
- custom UI and card assets built to fit the mod
- standard affinity gain through completing a game, win or lose (up to daily max)
- ...And much more! See the each release's changelog for more details.

### ...But why did you build this?

I wanted to provide the community a compelling way to ~~_perform the Sisyphean task of grinding her affinity over multiple months_~~ foster a more meaningful camaraderie and friendship with Natsuki than listening to her hamsters speech for the 500th time, like I had to. (_And god help you if you beat her in **Snap** four times in a row..._)

That, and as soon as the concept of "1v1 Uno on tap whenever I want it" occurred to me my fate was pretty much sealed!

<p align="center">
  <img src="media/jn-ichi-preview2.gif" alt="Ichi gameplay preview 2" width="100%">
</p>


### Great! How do I unlock it?

Ichi follows vanilla logic for minigames. It's introduced through a one-time greeting scene, and gameplay is found under the "Games" topic. To encourage engaging with the vanilla content first, Ichi depends on you having already unlocked the two existing minigames. These are the unlock criteria for the Ichi introduction:
- Reaching **HAPPY** affinity with Natsuki
- Launch the **Snap** topic at least 3 times
- Launch the **Blackjack** topic at least 3 times
- Exhaust all queued "special" vanilla greetings content (holidays, unlocks, etc.)
- After that, the Ichi intro will queue for the next eligible boot sequence
  
Beyond this are unlockable features. The first unlocks after completing 3 rounds of Ichi, win or lose. Once you complete one game of the resulting game mode, win or lose, you unlock a new mode. Have fun!

___

## Installation

1. Just to beat that dead horse, **back up your persistent data first.** [Here's how to back up your JN persistent file.](https://github.com/Just-Natsuki-Team/NatsukiModDev/wiki/04:-FAQ#can-i-back-up-my-save-data--how-do-i-find-my-persistent)

2. Download the latest test build from **Releases**.

3. Copy `script-ichi.rpy` into your `game/` folder.

4. Copy the included Ichi asset folders into the matching `game/mod_assets/...` locations.

5. Launch **Just Natsuki**.

6. Meet the unlock criteria and watch the one-time introduction.

7. Ask Natsuki to play Ichi through the **Games** topic.

8. Enjoy!

---

## Upcoming Features (Maybe)
After 80 hours minimum on coding, designing, testing, and writing this, the core game is here and complete and if I stopped right here it's completely rock-solid and feature-complete. Plus, my other submods need my love and so does my main DDLC story mod, so these are more notes for me than teasers for you. 

However, I never know to leave well enough alone, so I *am* napkin-scribbling some future concepts, such as...

- Potential additional gameplay modes (including new gameplay cards)
- Bluffs and catch penalties so Natsuki can pull a fast one on you, and vice versa
- Even more banter and affinity-tier content (because 800+ new lines of dialogue wasn't enough?)
- Integration with my other upcoming submods

---

## Bug reports

If you run into a bug, please report it in this repository and include:

- what happened
- what you were doing right before it happened
- the traceback, if the game threw one
- any house rules in play at the time

Basically... if it breaks, bring me your receipts.

---

## Credits

- **Team Salvato** for Doki Doki Literature Club
- The **Just Natsuki Team** for their hard work on this mod
- Dmitry Fomin over at Wikimedia Commons [for the cards and the super generous license](https://commons.wikimedia.org/wiki/File:UNO_cards_deck.svg#)
- And my super helpful beta testers: yes.exe, Humanbean
