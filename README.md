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
- in-character rules explanation
- tsundere banter action during play
- rematches, forfeits, and win/loss scenes
- custom UI and card assets built to fit the mod

Because this is a pre-release build, ***Ichi*** **is currently locked until you have unlocked the** ***Snap*** **minigame**. Speaking of pre-release...
___

## Pre-release testing build (v0.9)

This repository currently exists for **testing and bug reporting** before the main release.

The submod is playable and feature-complete for its current scope, but this is still a beta-style build. 

If anything weird, cursed, or "oops" happens, let me know so I can fix that. That said, it's already been pretty beta-tested, and I've already played, like, 50 rounds of this without issues. But my machine isn't your machine, etc.

___

<p align="center">
  <img src="media/jn-ichi-preview2.gif" alt="Ichi gameplay preview 2" width="100%">
</p>

## Current Features
Enjoy feature-complete, single-round Ichi gameplay playable directly through the **Games** topic.

- In-character rules explanation
- In-game banter throughout the match
- AI card choice and turn logic
- Tier-based tsundere content
- Wild Draw Four legality enforcement
- Deck reshuffling when needed
- Win, loss, rematch, and forfeit dialogue
- Standard affinity gain through completing a round, win or lose
- Only a *single* persistent write (adding the game to the topics database)

---

## Upcoming Features
The core game is here and ready, but a few extra rule systems are being saved for the full release.

- A proper in-game reveal
- House rules
- Advanced Ichi with score carryover in "Race to 500 points" style
- Ichi-specific persistent data and games tracking
- Bluffs and catch penalties
- Even more banter and affinity-tier content
- Integration with my other upcoming submods

---

## Installation

1. **Back up your persistent data first.** [How to back up your JN persistent file](https://github.com/Just-Natsuki-Team/NatsukiModDev/wiki/04:-FAQ#can-i-back-up-my-save-data--how-do-i-find-my-persistent)

2. Download the latest test build from **Releases**.

3. Copy `script-ichi.rpy` into your `game/` folder.

4. Copy the included Ichi asset folders into the matching `game/mod_assets/...` locations.

5. Launch **Just Natsuki**.

6. Ask Natsuki to play Ichi through the **Games** topic.

7. Enjoy!

---

## Bug reports

If you run into a bug, please report it in this repository and include:

- what happened
- what you were doing right before it happened
- the traceback, if the game threw one

Basically: if it breaks, bring receipts.

---

## Credits

- **Team Salvato** for Doki Doki Literature Club
- The **Just Natsuki Team** for their hard work on this mod
- Dmitry Fomin over at Wikimedia Commons [for the cards and the super generous license](https://commons.wikimedia.org/wiki/File:UNO_cards_deck.svg#)
- Everyone helping test a pre-release card game on purpose
