# script-ichi.rpy
# - https://github.com/Zhaumbie/Ichi-for-Just-Natsuki

# v0.9 scope notes:
# - Single-round Ichi only. No score carryover or race to 500.
# - Minimal persistent data writes.
# - Wild Draw Four legality is enforced.
# - Formal Wild Draw Four challenge flow is scaffolded but disabled.
# - UNO call / catch penalties are not implemented in this version.
# - No vanilla files are modified; all behavior lives in this submod file.

init -1 python:
    import store.jn_affinity as jn_affinity
    import store.jn_apologies as jn_apologies
    import store.jn_desk_items as jn_desk_items
    import store.jn_utils as jn_utils

init 1 python:
    try:
        _jn_ichi_original_quitInputCheck = quitInputCheck

    except NameError:
        _jn_ichi_original_quitInputCheck = None

    def quitInputCheck():
        # Ichi extension for JN's force-quit protection.
        # Keep this in the submod so we do not have to edit base files just to
        # register Ichi's gameplay screens as blocked.
        for blocked_screen in (
            "ichi_ui",
            "ichi_table_hand",
            "ichi_tutorial_cards"
        ):
            if renpy.get_screen(blocked_screen):
                Natsuki.setForceQuitAttempt(True)
                Natsuki.addApology(jn_apologies.ApologyTypes.sudden_leave)
                Natsuki.setQuitApology(jn_apologies.ApologyTypes.sudden_leave)
                return

        if _jn_ichi_original_quitInputCheck is not None:
            _jn_ichi_original_quitInputCheck()

    try:
        _jn_ichi_original_calculatedAffinityGain = Natsuki.calculatedAffinityGain

    except NameError:
        _jn_ichi_original_calculatedAffinityGain = None

    def _jn_ichi_shouldSuppressTopicAffinityGain():
        # Suppress the automatic topic-selection affinity gain when the player
        # clicks the Ichi topic from the Games menu.
        #
        # We only want to block that one gain granted before talk_play_ichi
        # starts. We do not want to block the normal gain awarded at the end
        # of a completed Ichi round.
        if Natsuki.isInGame():
            return False

        if not hasattr(persistent, "_event_list"):
            return False

        if not persistent._event_list:
            return False

        return persistent._event_list[0] == "talk_play_ichi"

    def _jn_ichi_calculatedAffinityGain(base=1, bypass=False):
        # Block the standard talk-topic gain for Ichi topic selection only.
        # All other affinity gains should pass through untouched.
        if _jn_ichi_shouldSuppressTopicAffinityGain():
            return

        if _jn_ichi_original_calculatedAffinityGain is not None:
            return _jn_ichi_original_calculatedAffinityGain(
                base=base,
                bypass=bypass
            )

    if _jn_ichi_original_calculatedAffinityGain is not None:
        Natsuki.calculatedAffinityGain = staticmethod(
            _jn_ichi_calculatedAffinityGain
        )

init 0 python in jn_ichi:
    from Enum import Enum
    import random
    import store

    ASSET_ROOT = "mod_assets/games/ichi"

    CARD_WIDTH = 223
    CARD_HEIGHT = 334

    CARD_BACK = ASSET_ROOT + "/back.png"

    COLOR_PINK = "pink"
    COLOR_BLUE = "blue"
    COLOR_PURPLE = "purple"
    COLOR_GREEN = "green"

    COLORS = [
        COLOR_PINK,
        COLOR_BLUE,
        COLOR_PURPLE,
        COLOR_GREEN
    ]

    VALUE_STOP = "stop"
    VALUE_REVERSE = "reverse"
    VALUE_DRAW_TWO = "draw_two"
    VALUE_WILD = "wild"
    VALUE_WILD_DRAW_FOUR = "wild_draw_four"

    class JNIchiStates(Enum):
        forfeit = 1
        natsuki_win = 2
        player_win = 3

    _controls_enabled = False
    _is_player_turn = True
    _game_state = None

    _deck = []
    _discard_pile = []
    _player_hand = []
    _natsuki_hand = []

    _selected_index = None
    _hovered_index = None
    _turn_drawn = False
    _drawn_card_index = None
    _must_choose_color = False

    _current_color = None

    # Only used when the player plays WD4 and Natsuki may challenge.
    # This scaffolding is intentionally left in place for later house-rule work.
    _pending_challenge = False
    _pending_wild_draw_four_by_player = None
    _pending_wild_draw_four_previous_color = None
    _pending_wild_draw_four_player_used_drawn_card = False

    _queued_quips = []
    _deck_warned_low = False
    _deck_warned_critical = False
    _pending_reshuffle = False


    def _clear():
        # Full runtime reset for a fresh game or clean exit.
        # This should only touch Ichi state, not persistent/player data.
        global _controls_enabled
        global _is_player_turn
        global _game_state
        global _selected_index
        global _hovered_index
        global _turn_drawn
        global _drawn_card_index
        global _must_choose_color
        global _current_color
        global _pending_challenge
        global _pending_wild_draw_four_by_player
        global _pending_wild_draw_four_previous_color
        global _pending_wild_draw_four_player_used_drawn_card
        global _deck_warned_low
        global _deck_warned_critical
        global _pending_reshuffle

        _controls_enabled = False
        _is_player_turn = True
        _game_state = None
        _selected_index = None
        _hovered_index = None
        _turn_drawn = False
        _drawn_card_index = None
        _must_choose_color = False
        _current_color = None
        _pending_challenge = False
        _pending_wild_draw_four_by_player = None
        _pending_wild_draw_four_previous_color = None
        _pending_wild_draw_four_player_used_drawn_card = False
        _deck_warned_low = False
        _deck_warned_critical = False
        _pending_reshuffle = False

        del _deck[:]
        del _discard_pile[:]
        del _player_hand[:]
        del _natsuki_hand[:]
        del _queued_quips[:]

    def _makeCard(color, value):
        if color is None:
            if value == VALUE_WILD:
                asset_name = "wild.png"

            else:
                asset_name = "wild_draw_four.png"

        else:
            asset_name = "{0}_{1}.png".format(color, value)

        return {
            "color": color,
            "value": value,
            "path": "{0}/{1}".format(ASSET_ROOT, asset_name)
        }

    def _isNumberCard(card):
        return card["value"] in [
            "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"
        ]

    def _buildDeck():
        del _deck[:]

        for color in COLORS:
            _deck.append(_makeCard(color, "0"))

            for number in range(1, 10):
                _deck.append(_makeCard(color, str(number)))
                _deck.append(_makeCard(color, str(number)))

            for _i in range(2):
                _deck.append(_makeCard(color, VALUE_STOP))
                _deck.append(_makeCard(color, VALUE_REVERSE))
                _deck.append(_makeCard(color, VALUE_DRAW_TWO))

        for _i in range(4):
            _deck.append(_makeCard(None, VALUE_WILD))
            _deck.append(_makeCard(None, VALUE_WILD_DRAW_FOUR))

        random.shuffle(_deck)

    def _drawCards(is_player, amount):
        hand = _player_hand if is_player else _natsuki_hand
        drawn_cards = []

        for _i in range(amount):
            if len(_deck) == 0:
                break

            new_card = _deck.pop()
            hand.append(new_card)
            drawn_cards.append(new_card)

        if len(drawn_cards) > 0:
            renpy.play(
                "mod_assets/sfx/card_flip_{0}.ogg".format(random.choice(["a", "b", "c"]))
            )

        return drawn_cards

    def _setup():
        _clear()
        _buildDeck()

        _drawCards(True, 7)
        _drawCards(False, 7)

        # Open on a number card only to avoid messy first-turn action states.
        while len(_deck) > 0:
            opening_card = _deck.pop()

            if not _isNumberCard(opening_card):
                _deck.insert(0, opening_card)
                random.shuffle(_deck)
                continue

            _discard_pile.append(opening_card)

            global _current_color
            _current_color = opening_card["color"]
            break

        global _is_player_turn
        _is_player_turn = random.choice([True, False])

    def _getTopDiscardCard():
        if len(_discard_pile) > 0:
            return _discard_pile[-1]

        return None

    def _getTopDiscardPath():
        top_card = _getTopDiscardCard()
        return top_card["path"] if top_card else CARD_BACK

    def _getScaledCardDisplayable(card_path):
        return renpy.display.im.Scale(card_path, CARD_WIDTH, CARD_HEIGHT)

    def _getCurrentColorDisplayName():
        return {
            COLOR_PINK: "Pink",
            COLOR_BLUE: "Blue",
            COLOR_PURPLE: "Purple",
            COLOR_GREEN: "Green"
        }.get(_current_color, "Wild")

    def _getValueDisplayName(value):
        return {
            VALUE_STOP: "Stop",
            VALUE_REVERSE: "Reverse",
            VALUE_DRAW_TWO: "Draw Two",
            VALUE_WILD: "Wild",
            VALUE_WILD_DRAW_FOUR: "Wild Draw Four"
        }.get(value, value)

    def _getColorCountMap(hand):
        color_counts = {
            COLOR_PINK: 0,
            COLOR_BLUE: 0,
            COLOR_PURPLE: 0,
            COLOR_GREEN: 0
        }

        for card in hand:
            if card["color"] in color_counts:
                color_counts[card["color"]] += 1

        return color_counts

    def _getBestColorForHand(hand):
        color_counts = _getColorCountMap(hand)
        highest = max(color_counts.values())

        if highest <= 0:
            return random.choice(COLORS)

        best_colors = []

        for color in COLORS:
            if color_counts[color] == highest:
                best_colors.append(color)

        return random.choice(best_colors)

    def _handHasColor(hand, color_name):
        if color_name is None:
            return False

        for card in hand:
            if card["color"] == color_name:
                return True

        return False

    def _canLegallyPlayWildDrawFour(hand, index, previous_color=None):
        if not 0 <= index < len(hand):
            return False

        if hand[index]["value"] != VALUE_WILD_DRAW_FOUR:
            return True

        if previous_color is None:
            previous_color = _current_color

        return not _handHasColor(hand, previous_color)

    def _cardMatches(card, hand=None, index=None):
        top_card = _getTopDiscardCard()

        if top_card is None:
            return True

        if card["value"] == VALUE_WILD_DRAW_FOUR:
            if hand is None or index is None:
                return False

            if not _canLegallyPlayWildDrawFour(hand, index):
                return False

            return True

        if card["color"] is None:
            return True

        if card["color"] == _current_color:
            return True

        if card["value"] == top_card["value"]:
            return True

        return False

    def _getPlayableIndices(hand):
        playable = []

        for index, card in enumerate(hand):
            if _cardMatches(card, hand, index):
                playable.append(index)

        return playable

    def _canPlayerSelectCard(index):
        if not _is_player_turn or not _controls_enabled or _must_choose_color:
            return False

        # WD4 challenge path intentionally inactive in this beta build.
        # if _pending_challenge:
        #     return False

        if not 0 <= index < len(_player_hand):
            return False

        if _turn_drawn:
            return index == _drawn_card_index

        return True

    def _setSelectedIndex(index):
        global _selected_index

        if not _canPlayerSelectCard(index):
            return

        if _selected_index == index:
            _selected_index = None

        else:
            _selected_index = index

        renpy.restart_interaction()

    def _setHoveredIndex(index):
        global _hovered_index
        _hovered_index = index

    def _clearHoveredIndex():
        global _hovered_index
        _hovered_index = None

    def _toSittingExpression(expression_code):
        # Gameplay-only helper.
        # Keeps in-game Ichi quips and reshuffle dialogue in sitting pose 1.
        # Do not use this for pre-game, explanation, or post-game authored dialogue.
        if expression_code and len(expression_code) > 0:
            return "1" + expression_code[1:]

        return expression_code

    def _queueQuip(expression_code, text):
        # Queue a gameplay quip for ichi_show_quips.
        # All queued quips are forced into sitting pose 1 because they fire
        # while the table UI is already up.
        if text is None:
            text = ""

        _queued_quips.append((
            _toSittingExpression(expression_code),
            renpy.substitute(text)
        ))

    def _chooseDialogueBlock(blocks):
        # Pick one authored block at once so expression/line pairs stay together.
        return random.choice(blocks)

    def _deckCanRefillFromDiscard():
        return len(_deck) == 0 and len(_discard_pile) > 1

    def _checkDeckThresholds():
        global _deck_warned_low
        global _deck_warned_critical
        global _pending_reshuffle

        deck_count = len(_deck)

        if deck_count == 0 and len(_discard_pile) > 1:
            _pending_reshuffle = True
            return

        if deck_count <= 10 and not _deck_warned_critical:
            _deck_warned_critical = True
            _queueDeckWarningQuip(True)
            return

        if deck_count <= 15 and not _deck_warned_low:
            _deck_warned_low = True
            _queueDeckWarningQuip(False)

    def _queueDeckWarningQuip(is_critical):
        # Low-deck chatter is queued, not spoken immediately.
        # That keeps it in the same delivery path as normal gameplay quips.
        tier = _getAffinityDialogueTier()

        if is_critical:
            if tier == "love":
                block = _chooseDialogueBlock([
                    [("1nchss", "Wow. We are seriously burning through this deck."), ("1fsqsm", "If we run it dry, I'm reshuffling and we're finishing this properly, got it?")],
                    [("1unmaj", "Nnn. Hardly anything left now."), ("1fchsm", "Good. Means this game's getting interesting.")]
                ])

            elif tier == "enamored":
                block = _chooseDialogueBlock([
                    [("1tlrss", "Okay. Deck's getting dangerously thin."), ("1fsqsm", "Try not to act shocked when I reshuffle and still beat you.")],
                    [("1tlrss", "Not much left now, huh?"), ("1fchbg", "Heh. Guess we're really tearing through it.")]
                ])

            elif tier == "affectionate":
                block = _chooseDialogueBlock([
                    [("1nwmss", "Okay. We're getting really low now."), ("1fsqsm", "So don't zone out on me if I have to reshuffle.")],
                    [("1ulraj", "Huh. Hardly any deck left."), ("1nchbs", "At least that means the game's moving.")]
                ])

            else:
                block = _chooseDialogueBlock([
                    [("1ulrss", "We're almost out of deck already."), ("1fsqsm", "So pay attention when I reshuffle it.")],
                    [("1unmaj", "Not much left now."), ("1fcssm", "Good. Let's keep this moving.")]
                ])

        else:
            if tier == "love":
                block = _chooseDialogueBlock([
                    [("1unmaj", "Heh. We've already chewed through a lot of the deck."), ("1fcssm", "Guess we're both actually trying today.")],
                    [("1nchsm", "Deck's starting to look a little thin."), ("1uchsm", "Don't worry. I've got it under control.")]
                ])

            elif tier == "enamored":
                block = _chooseDialogueBlock([
                    [("1unmaj", "Wow. We've gone through a lot already."), ("1fcssm", "Not bad, [player].")],
                    [("1nchsm", "Deck's getting low."), ("1fsqsm", "Try not to fall apart when it gets messy.")]
                ])

            elif tier == "affectionate":
                block = _chooseDialogueBlock([
                    [("1unmaj", "Huh. Deck's starting to run low."), ("1fcssm", "Guess we're not messing around anymore.")],
                    [("1nchsm", "We're burning through cards pretty fast."), ("1fsqsm", "Try to keep up.")]
                ])

            else:
                block = _chooseDialogueBlock([
                    [("1unmaj", "Deck's starting to run low."), ("1fsqsm", "So don't get sloppy.")],
                    [("1nchsm", "We're chewing through cards pretty fast."), ("1fcssm", "Good. Keeps things interesting.")]
                ])

        _queued_quips.extend([
            (_toSittingExpression(block[0][0]), renpy.substitute(block[0][1])),
            (_toSittingExpression(block[1][0]), renpy.substitute(block[1][1]))
        ])

    def _performDeckReshuffle():
        global _pending_reshuffle
        global _deck_warned_low
        global _deck_warned_critical

        if not _deckCanRefillFromDiscard():
            _pending_reshuffle = False
            return False

        top_card = _discard_pile.pop()

        while len(_discard_pile) > 0:
            _deck.append(_discard_pile.pop())

        random.shuffle(_deck)
        _discard_pile.append(top_card)

        _pending_reshuffle = False
        _deck_warned_low = False
        _deck_warned_critical = False
        return True

    def _getAffinityDialogueTier():
        if store.Natsuki.isLove(higher=True):
            return "love"

        elif store.Natsuki.isEnamored(higher=True):
            return "enamored"

        elif store.Natsuki.isAffectionate(higher=True):
            return "affectionate"

        else:
            return "happy"

    def _queueBasicPlayQuip(is_player):
        if is_player:
            _queueQuip(
                random.choice(["1fsqsm", "1nwrsm", "1fchsm", "1uchsm"]),
                random.choice([
                    "Ehehe. Nice try, [player].",
                    "Yeah, yeah. I saw that.",
                    "Feeling real confident over there, huh?",
                    "Not bad. Still won't be enough to beat me.",
                    "Hmph. Keep going.",
                    "Is that the worst you can do?",
                    "Is that really all you've got?",
                    "C'mon. Make me try for it.",
                    "Sheesh.",
                    "I'm having fun! Hope you are too.",
                    "Don't get cocky just because that one worked.",
                    "You really think that's gonna scare me?",
                    "Finally waking up, huh?",
                    "Keep that up and I {i}might{/i} start taking you seriously."
                ])
            )

        else:
            _queueQuip(
                random.choice(["1fchbg", "1uchsm", "1fsqsm", "1nwrsm"]),
                random.choice([
                    "Your turn now.",
                    "Your move, [player].",
                    "Alright. Show me what you've got.",
                    "Let's see what you do with that.",
                    "Do your worst, [player].",
                    "Just you wait.",
                    "We can call it now if you wanna forfeit.",
                    "Ehehe. Go on, then.",
                    "Don't get sore on me now.",
                    "Hope you're ready to lose.",
                    "Try not to choke on the pressure, okay?"
                ])
            )

    def _queueStopQuip(is_player, is_reverse):
        action_name = "Reverse" if is_reverse else "Stop"

        if is_player:
            chosen_line = random.choice([
                "Seriously? Playing a __ACTION__?",
                "Hey! No fair.",
                "Nnnn... cheap move.",
                "Yeah, okay. Rub it in.",
                "...Maybe I deserved that.",
                "Oh, just you wait, [player].",
                "Ugh!",
                "{i}Excuse{/i} me?",
                "Wow. A __ACTION__. Real original.",
                "You {i}would{/i} throw a __ACTION__ at me right now.",
                "Fine! Hide behind your little __ACTION__ card.",
                "Enjoy that while you can.",
                "If this flips the game, I'm blaming that stupid __ACTION__."
            ])

            _queueQuip(
                random.choice(["1ccsfl", "1csqsm", "1fsqsm"]),
                chosen_line.replace("__ACTION__", action_name)
            )

        else:
            chosen_line = random.choice([
                "And I'm going again, [player].",
                "Nope! My turn again.",
                "Tough luck, [player].",
                "Heh. Not moving so fast now, huh?",
                "Almost feel bad about that. Well... not really.",
                "Ahahahaha! Take some of {i}that!{/i}",
                "You know what you did.",
                "I expected that to feel better. Oh well.",
                "__ACTION__ chains are my favorite kind.",
                "Hey, you can cheer from the sidelines if you want.",
                "Guess you're on timeout now.",
                "Start planning for your next game while I'm busy winning this one."
            ])

            _queueQuip(
                random.choice(["1fsqsm", "1fchbg", "1nwrsm"]),
                chosen_line.replace("__ACTION__", action_name)
            )

    def _queueDrawTwoQuip(is_player):
        if is_player:
            _queueQuip(
                random.choice(["1ccsfl", "1csqsm", "1fsqsm"]),
                random.choice([
                    "Oh, come on... Draw Two?",
                    "Yeah, yeah. I see it.",
                    "Nnnn... lucky you.",
                    "Fine. Have your little Draw Two.",
                    "You had to pick {i}that{/i} now, huh?",
                    "Tch. Cheap.",
                    "Really? A Draw Two?",
                    "You're enjoying this way too much.",
                    "Okay. I hate that.",
                    "This better come back around on you."
                ])
            )

        else:
            _queueQuip(
                random.choice(["1fchbg", "1fsqsm", "1nwrsm"]),
                random.choice([
                    "Pick up two, [player].",
                    "Yep. Draw Two.",
                    "That stings, huh?",
                    "Go ahead. Take them.",
                    "You can blame the deck if it makes you feel better.",
                    "Looks heavy. Better get both.",
                    "Aw. Need help carrying those?",
                    "Don't worry. I'm sure four hands would suit you.",
                    "This is why I keep these around.",
                    "Take your medicine."
                ])
            )

    def _queueWildQuip(is_player):
        color_name = _getCurrentColorDisplayName()

        if is_player:
            _queueQuip(
                random.choice(["1fsqsm", "1nwrsm", "1fcssm"]),
                random.choice([
                    color_name + "? Fine.",
                    "Of course you'd pick " + color_name + ".",
                    color_name + ", huh? Real subtle.",
                    "Yeah, yeah. " + color_name + ". I got it.",
                    color_name + "? Sure. Twist the knife.",
                    "Okay. " + color_name + ". Noted.",
                    "Real creative. " + color_name + ".",
                    color_name + " again? Hmph.",
                    "Fine. " + color_name + " it is.",
                    color_name + "? You always do this."
                ])
            )

        else:
            _queueQuip(
                random.choice(["1fchbg", "1uchsm", "1fsqsm"]),
                random.choice([
                    color_name + ". Deal with it, [player].",
                    "Let's go with " + color_name + ".",
                    color_name + ". Yep. That's what we're doing.",
                    color_name + ", obviously.",
                    "Changing it to " + color_name + ".",
                    color_name + ". Try not to cry about it.",
                    "We're doing " + color_name + " now.",
                    color_name + ". Keep up.",
                    "I pick " + color_name + ".",
                    color_name + ". Good luck."
                ])
            )

    def _queueWildDrawFourQuip(is_player):
        if is_player:
            _queueQuip(
                random.choice(["1ccsfl", "1csqsm", "1fsqsm"]),
                random.choice([
                    "Wild Draw Four? Seriously?",
                    "Yeah, okay. That's rude.",
                    "Nnnn... real classy.",
                    "Of course you'd drop that now.",
                    "Wow. You really went for it.",
                    "You weren't saving that for a better moment?",
                    "Tch. That's obnoxious.",
                    "You just had to throw the worst one.",
                    "I hate that card.",
                    "That is such a cheap swing."
                ])
            )

        else:
            _queueQuip(
                random.choice(["1fchbg", "1fsqsm", "1nwrsm"]),
                random.choice([
                    "Wild Draw Four. Deal with it, [player].",
                    "Oh, you're gonna hate this one.",
                    "Here. Have four.",
                    "Ehehe. That one hurts.",
                    "This should slow you down.",
                    "Go on. Pick up four.",
                    "Bet you wish this was your card.",
                    "Now {i}that's{/i} a move.",
                    "You looked too comfortable.",
                    "Let's make your hand uglier."
                ])
            )

    def _queueChallengeQuip(success, player_challenged):
        if player_challenged:
            if success:
                _queueQuip(
                    random.choice(["1fchbg", "1fsqsm", "1nwrsm"]),
                    random.choice([
                        "Ha! Caught you.",
                        "Knew it.",
                        "Nice try, [player].",
                        "You weren't getting away with that.",
                        "Busted.",
                        "That's what you get for bluffing.",
                        "I knew you were pulling something.",
                        "Ehehe. Got you.",
                        "Seriously? You thought that would work?",
                        "Not slick enough."
                    ])
                )

            else:
                _queueQuip(
                    random.choice(["1fchbg", "1uchsm", "1nwmsm"]),
                    random.choice([
                        "Ehehe. Wrong call.",
                        "Told you.",
                        "That backfired pretty hard, huh?",
                        "Should've just taken the four.",
                        "Whoops. Bad gamble.",
                        "You really thought I messed that up?",
                        "That one is on you.",
                        "Bold move. Dumb one, but bold.",
                        "Should've trusted the card.",
                        "Nice self-own."
                    ])
                )

        else:
            if success:
                _queueQuip(
                    random.choice(["1ccsfl", "1csqsm", "1nslpo"]),
                    random.choice([
                        "Tch. Fine.",
                        "Seriously?",
                        "Ugh... alright.",
                        "That was annoying.",
                        "I hate that you were right.",
                        "Okay. That sucked.",
                        "Whatever.",
                        "I'm still blaming the deck.",
                        "That was stupid.",
                        "You got lucky."
                    ])
                )

            else:
                _queueQuip(
                    random.choice(["1fchbg", "1fsqsm", "1nwrsm"]),
                    random.choice([
                        "Ehehe. Busted.",
                        "Bad challenge, [player].",
                        "You really thought I messed that up?",
                        "Nice try.",
                        "Didn't work, huh?",
                        "Should've kept your mouth shut.",
                        "Nope. Not this time.",
                        "That one blew up in your face.",
                        "Guess I was legal after all.",
                        "Try again next time."
                    ])
                )

    def _queueIchiQuip(is_player):
        if is_player:
            _queueQuip(
                random.choice(["1fsqsm", "1ftrsm", "1fcssm"]),
                random.choice([
                    "Already? Don't get smug yet, [player].",
                    "Ichi, huh? Big deal.",
                    "Yeah, I heard you. Ichi.",
                    "One card left? Hmph.",
                    "It's not over yet!",
                    "I wouldn't get cocky yet if I were you.",
                    "Down to one card? Hah! It ain't over 'til it's over!",
                    "Go on, announce it louder. See if that helps.",
                    "Enjoy it while it lasts, okay?",
                    "One card left, huh? I'm not letting you have it that easy."
                ])
            )

        else:
            _queueQuip(
                random.choice(["1fchbg", "1nwrbg", "1fsqsm"]),
                random.choice([
                    "Ichi! Ehehe.",
                    "One card left! Ichi!",
                    "Ichi, [player]!",
                    "Heh. Ichi.",
                    "Guess who's got two hands and one card? Me. Ichi!",
                    "Ichi! Better start panicking, 'cause I'm not slowing down.",
                    "Ichi! You can still catch up, you know... maybe.",
                    "One card left! Try not to mess up before I finish this.",
                    "You hear that? That's the sound of you losing. And it sounds {i}great{/i}.",
                    "Go ahead and pray I draw something dumb next."
                ])
            )

    def _updateGameState():
        global _game_state

        if len(_player_hand) == 0:
            _game_state = JNIchiStates.player_win

        elif len(_natsuki_hand) == 0:
            _game_state = JNIchiStates.natsuki_win

    def _finishTurnAfterPlayerPlay():
        global _turn_drawn
        global _drawn_card_index
        global _selected_index
        global _must_choose_color

        _turn_drawn = False
        _drawn_card_index = None
        _selected_index = None
        _must_choose_color = False

    def _resolveActionCard(card, is_player, previous_color, player_used_drawn_card=False):
        # Apply the played card's gameplay effect.
        # In two-player Ichi, Stop and Reverse both function as "take another turn".
        # WD4 challenge scaffolding exists below, but is intentionally inactive.
        global _is_player_turn
        global _pending_challenge
        global _pending_wild_draw_four_by_player
        global _pending_wild_draw_four_previous_color
        global _pending_wild_draw_four_player_used_drawn_card

        if card["value"] == VALUE_STOP:
            _queueStopQuip(is_player, False)
            _is_player_turn = is_player

        elif card["value"] == VALUE_REVERSE:
            _queueStopQuip(is_player, True)
            _is_player_turn = is_player

        elif card["value"] == VALUE_DRAW_TWO:
            if is_player:
                _drawCards(False, 2)

            else:
                _drawCards(True, 2)

            _queueDrawTwoQuip(is_player)
            _is_player_turn = is_player

        elif card["value"] == VALUE_WILD:
            _queueWildQuip(is_player)
            _is_player_turn = not is_player

        elif card["value"] == VALUE_WILD_DRAW_FOUR:
            _queueWildDrawFourQuip(is_player)

            if is_player:
                _drawCards(False, 4)
                _is_player_turn = True

            else:
                _drawCards(True, 4)
                _is_player_turn = False

        else:
            _queueBasicPlayQuip(is_player)
            _is_player_turn = not is_player

    def _playCardFromHand(is_player, index, chosen_color=None):
        # Core card-resolution path.
        # Moves the card, updates color state, fires any action effect,
        # then updates turn/game state.
        global _current_color

        hand = _player_hand if is_player else _natsuki_hand

        if not 0 <= index < len(hand):
            return

        previous_color = _current_color
        player_used_drawn_card = is_player and _turn_drawn and index == _drawn_card_index

        card = hand.pop(index)
        _discard_pile.append(card)

        if card["color"] is None:
            _current_color = chosen_color

        else:
            _current_color = card["color"]

        renpy.play(
            "mod_assets/sfx/card_flip_{0}.ogg".format(random.choice(["a", "b", "c"]))
        )

        _resolveActionCard(card, is_player, previous_color, player_used_drawn_card)

        if is_player:
            _finishTurnAfterPlayerPlay()

        if len(hand) == 1:
            _queueIchiQuip(is_player)

        _updateGameState()
        renpy.restart_interaction()

    def _playSelected():
        global _must_choose_color

        if not _is_player_turn or not _controls_enabled:
            return

        # WD4 challenge path intentionally inactive in this beta build.
        # if _pending_challenge:
        #     return

        if _selected_index is None:
            return

        if _turn_drawn and _selected_index != _drawn_card_index:
            return

        if not 0 <= _selected_index < len(_player_hand):
            return

        selected_card = _player_hand[_selected_index]

        if not _cardMatches(selected_card, _player_hand, _selected_index):
            return

        if selected_card["color"] is None:
            _must_choose_color = True
            renpy.restart_interaction()
            return

        _playCardFromHand(True, _selected_index)

    def _choosePlayerColor(color_name):
        global _must_choose_color

        if not _must_choose_color:
            return

        if _selected_index is None or not 0 <= _selected_index < len(_player_hand):
            _must_choose_color = False
            renpy.restart_interaction()
            return

        _must_choose_color = False
        _playCardFromHand(True, _selected_index, color_name)

    def _canPlayerDrawOrPass():
        if not _is_player_turn or not _controls_enabled or _must_choose_color:
            return False

        # WD4 challenge path intentionally inactive in this beta build.
        # if _pending_challenge:
        #     return False

        if _turn_drawn:
            return False

        return True

    def _playerDrawOrPass():
        global _is_player_turn
        global _turn_drawn
        global _drawn_card_index
        global _selected_index

        if not _is_player_turn or not _controls_enabled or _must_choose_color:
            return

        # WD4 challenge path intentionally inactive in this beta build.
        # if _pending_challenge:
        #     return

        if _turn_drawn:
            return

        drawn_cards = _drawCards(True, 1)

        if len(drawn_cards) <= 0:
            _is_player_turn = False
            renpy.restart_interaction()
            return

        drawn_index = len(_player_hand) - 1
        drawn_card = _player_hand[drawn_index]

        if _cardMatches(drawn_card, _player_hand, drawn_index):
            _turn_drawn = True
            _drawn_card_index = drawn_index
            _selected_index = drawn_index

        else:
            _turn_drawn = False
            _drawn_card_index = None
            _selected_index = None
            _is_player_turn = False

        renpy.restart_interaction()

    def _getSelectedCardHelp():
        if _must_choose_color:
            return "Pick a color."

        if _selected_index is None or not 0 <= _selected_index < len(_player_hand):
            return "Select a card."

        selected_card = _player_hand[_selected_index]

        if _turn_drawn:
            if _selected_index != _drawn_card_index:
                return "You can only play the card you just drew."

            if _cardMatches(selected_card, _player_hand, _selected_index):
                return "You drew a playable card. You have to play it."

        if _cardMatches(selected_card, _player_hand, _selected_index):
            return "{0} is playable.".format(_getValueDisplayName(selected_card["value"]))

        return "{0} is not playable.".format(_getValueDisplayName(selected_card["value"]))

    def _getDrawButtonLabel():
        return "Draw"

    def _canPlaySelected():
        if not _is_player_turn or not _controls_enabled or _must_choose_color:
            return False

        # WD4 challenge path intentionally inactive in this beta build.
        # if _pending_challenge:
        #     return False

        if _selected_index is None or not 0 <= _selected_index < len(_player_hand):
            return False

        if _turn_drawn and _selected_index != _drawn_card_index:
            return False

        return _cardMatches(_player_hand[_selected_index], _player_hand, _selected_index)

    def _canForfeit():
        return (
            _is_player_turn
            and _controls_enabled
            and not _must_choose_color
        )

        # WD4 challenge path intentionally inactive in this beta build.
        # and not _pending_challenge

    def _requestForfeit():
        if _canForfeit():
            renpy.jump("ichi_forfeit")

    def _aiChoosePlayableIndex():
        playable_indices = _getPlayableIndices(_natsuki_hand)

        if len(playable_indices) <= 0:
            return None

        best_index = playable_indices[0]
        best_score = -999

        for index in playable_indices:
            card = _natsuki_hand[index]
            score = 0
            remaining_colors = _getColorCountMap(_natsuki_hand)
            top_card = _getTopDiscardCard()
            top_value = top_card["value"] if top_card else None

            if card["color"] is not None:
                score += remaining_colors.get(card["color"], 0) * 2

            if card["value"] == VALUE_STOP or card["value"] == VALUE_REVERSE:
                score += 5

            elif card["value"] == VALUE_DRAW_TWO:
                score += 7

            elif card["value"] == VALUE_WILD:
                score += 3

            elif card["value"] == VALUE_WILD_DRAW_FOUR:
                score += 8

            if len(_player_hand) <= 3:
                if card["value"] == VALUE_STOP or card["value"] == VALUE_REVERSE:
                    score += 8

                elif card["value"] == VALUE_DRAW_TWO:
                    score += 10

                elif card["value"] == VALUE_WILD_DRAW_FOUR:
                    score += 12

            if len(_natsuki_hand) <= 3 and card["color"] is None:
                score += 5

            if top_value is not None and card["value"] == top_value:
                score += 1

            if card["value"] == VALUE_WILD and len(_natsuki_hand) > 4:
                score -= 2

            if card["value"] == VALUE_WILD_DRAW_FOUR and len(_natsuki_hand) > 3:
                score -= 3

            if score > best_score:
                best_score = score
                best_index = index

        return best_index

    # WD4 challenge leg intentionally left in place for future work.
    # It is not wired up in this beta build.
    def _shouldAIChallengeWildDrawFour():
        remaining_player_cards = len(_player_hand)
        estimated_has_old_color = 1.0 - pow(0.75, max(1, remaining_player_cards))

        if _pending_wild_draw_four_player_used_drawn_card:
            estimated_has_old_color *= 0.35

        if remaining_player_cards <= 2:
            estimated_has_old_color += 0.08

        elif remaining_player_cards >= 6:
            estimated_has_old_color += 0.05

        estimated_has_old_color = max(0.10, min(0.82, estimated_has_old_color))
        return random.random() < estimated_has_old_color

    def _aiResolveWildDrawFourChallenge():
        global _pending_challenge
        global _pending_wild_draw_four_by_player
        global _pending_wild_draw_four_previous_color
        global _pending_wild_draw_four_player_used_drawn_card
        global _is_player_turn

        if not _pending_challenge or _is_player_turn:
            return False

        if not _shouldAIChallengeWildDrawFour():
            _drawCards(False, 4)
            _is_player_turn = True

            _pending_challenge = False
            _pending_wild_draw_four_by_player = None
            _pending_wild_draw_four_previous_color = None
            _pending_wild_draw_four_player_used_drawn_card = False

            _updateGameState()
            renpy.restart_interaction()
            return True

        previous_color = _pending_wild_draw_four_previous_color
        player_was_legal = not _handHasColor(_player_hand, previous_color)

        if not player_was_legal:
            _drawCards(True, 4)
            _queueChallengeQuip(True, True)
            _is_player_turn = False

        else:
            _drawCards(False, 6)
            _queueChallengeQuip(False, True)
            _is_player_turn = True

        _pending_challenge = False
        _pending_wild_draw_four_by_player = None
        _pending_wild_draw_four_previous_color = None
        _pending_wild_draw_four_player_used_drawn_card = False

        _updateGameState()
        renpy.restart_interaction()
        return True

    def _takeAITurn():
        # Simple AI turn flow:
        # 1) Choose the best playable card if one exists.
        # 2) Otherwise draw one.
        # 3) Immediately play the drawn card if legal.
        # 4) Otherwise pass turn back to the player.
        global _is_player_turn

        # WD4 challenge path intentionally inactive in this beta build.
        # if _pending_challenge and not _is_player_turn:
        #     if _aiResolveWildDrawFourChallenge():
        #         return

        playable_index = _aiChoosePlayableIndex()

        if playable_index is None:
            drawn_cards = _drawCards(False, 1)

            if len(drawn_cards) > 0:
                drawn_index = len(_natsuki_hand) - 1
                drawn_card = _natsuki_hand[drawn_index]

                if _cardMatches(drawn_card, _natsuki_hand, drawn_index):
                    chosen_color = _getBestColorForHand(_natsuki_hand) if drawn_card["color"] is None else None
                    _playCardFromHand(False, drawn_index, chosen_color)
                    return

            _is_player_turn = True
            renpy.restart_interaction()
            return

        chosen_card = _natsuki_hand[playable_index]
        chosen_color = _getBestColorForHand(_natsuki_hand) if chosen_card["color"] is None else None
        _playCardFromHand(False, playable_index, chosen_color)

    def _cleanupAfterGame():
        # Full cleanup for every exit path:
        # normal win/loss, cancel before start, or forfeit.
        renpy.hide_screen("ichi_ui")
        renpy.hide_screen("ichi_table_hand")
        renpy.hide_screen("ichi_tutorial_cards")

        # Always restore the hotkey overlay after Ichi ends.
        # The old conditional restore path was too brittle in topic/menu flows.
        if not renpy.get_screen("hkb_overlay"):
            store.HKBShowButtons()

        _clear()

        # Hand control back to normal JN conversation systems.
        store.Natsuki.setInGame(False)
        store.Natsuki.resetLastTopicCall()
        store.Natsuki.resetLastIdleCall()

transform ichi_hand_card:
    zoom 0.28

transform ichi_hand_card_hover:
    zoom 0.28
    yoffset -10

transform ichi_hand_card_selected:
    zoom 0.28
    yoffset -18

transform ichi_discard_card:
    zoom 0.82

transform ichi_nat_hand_card(rot=0, xsq=1.0):
    zoom 0.27
    xzoom xsq
    yzoom 1.0
    rotate rot
    alpha 0.99

transform ichi_tutorial_card_grid_card:
    zoom 0.58

screen ichi_tutorial_cards(card_paths):
    zorder 50

    $ _ichi_tutorial_positions = [
        (380, 0),
        (380, 240),
        (190, 0),
        (190, 240),
        (0, 0)
    ]

    fixed:
        xpos 700
        ypos 80

        for _idx, _card_path in enumerate(card_paths):
            if _idx < len(_ichi_tutorial_positions):
                $ _tutorial_pos = _ichi_tutorial_positions[_idx]

                add jn_ichi._getScaledCardDisplayable(_card_path):
                    xpos _tutorial_pos[0]
                    ypos _tutorial_pos[1]
                    at ichi_tutorial_card_grid_card

screen ichi_table_hand():
    zorder 1
    null

screen ichi_ui():
    # Do not make the gameplay UI modal.
    # When this screen is modal before the opening coin-flip dialogue,
    # Ren'Py can get stuck showing the board with no advancing dialogue.
    modal False
    zorder 8

    $ _ichi_current_color = jn_ichi._getCurrentColorDisplayName()
    $ _ichi_selected_help = jn_ichi._getSelectedCardHelp()
    $ _ichi_draw_button_label = jn_ichi._getDrawButtonLabel()
    $ _ichi_natsuki_hand_count = len(jn_ichi._natsuki_hand)
    $ _ichi_player_hand_count = len(jn_ichi._player_hand)
    $ _ichi_can_play_selected = jn_ichi._canPlaySelected()
    $ _ichi_can_draw_or_pass = jn_ichi._canPlayerDrawOrPass()
    $ _ichi_can_forfeit = jn_ichi._canForfeit()
    $ _ichi_is_player_turn = jn_ichi._is_player_turn
    $ _ichi_turn_text = "Yours!" if _ichi_is_player_turn else "{0}!".format(n_name)
    $ _ichi_is_picker = jn_ichi._must_choose_color

    $ _ichi_player_hand_step = 44
    $ _ichi_player_hand_right_x = 884
    $ _ichi_player_hand_y = 450

    $ _ichi_nat_visible_count = min(max(_ichi_natsuki_hand_count, 1), 7)
    $ _ichi_nat_hand_step = 18
    $ _ichi_nat_hand_center_x = 418
    $ _ichi_nat_hand_y = 556

    for _nat_loop in range(_ichi_nat_visible_count):
        $ _nat_delta = _nat_loop - ((_ichi_nat_visible_count - 1) / 2.0)
        $ _nat_x = int(_ichi_nat_hand_center_x + (_nat_delta * _ichi_nat_hand_step))
        $ _nat_rot = int(_nat_delta * 5)
        $ _nat_squish = max(0.95, 1.0 - (abs(_nat_delta) * 0.01))

        add jn_ichi._getScaledCardDisplayable(jn_ichi.ASSET_ROOT + "/back-natsuki.png"):
            anchor (0.5, 0.0)
            xpos _nat_x
            ypos _ichi_nat_hand_y
            at ichi_nat_hand_card(_nat_rot, _nat_squish)

    text "Color: [_ichi_current_color]":
        style "categorized_menu_button"
        size 28
        xcenter 1140
        ypos 28

    add jn_ichi._getScaledCardDisplayable(jn_ichi._getTopDiscardPath()):
        anchor (0, 0)
        pos (1055, 82)
        at ichi_discard_card

    text "Your hand: [_ichi_player_hand_count]" size 22 xpos 805 ypos 110 style "categorized_menu_button"
    text "[n_name]'s hand: [_ichi_natsuki_hand_count]" size 22 xpos 805 ypos 150 style "categorized_menu_button"
    text "Turn: [_ichi_turn_text]" size 22 xpos 805 ypos 215 style "categorized_menu_button"

    text "[_ichi_selected_help]":
        style "categorized_menu_button"
        size 20
        xcenter 755
        ypos 390
        xsize 500
        text_align 0.5

    style_prefix "hkb"

    if _ichi_is_picker:
        frame:
            xpos 1040
            ypos 402
            xsize 224
            padding (0, 0)
            background Solid("#000000AA")

            vbox:
                spacing 8
                xfill True

                null height 8

                text "Choose a color.":
                    style "categorized_menu_button"
                    size 20
                    xalign 0.5
                    xsize 224
                    text_align 0.5

                textbutton _("Pink"):
                    style "hkb_option"
                    xminimum 200
                    xmaximum 200
                    xalign 0.5
                    text_xalign 0.5
                    action Function(jn_ichi._choosePlayerColor, jn_ichi.COLOR_PINK)

                textbutton _("Blue"):
                    style "hkb_option"
                    xminimum 200
                    xmaximum 200
                    xalign 0.5
                    text_xalign 0.5
                    action Function(jn_ichi._choosePlayerColor, jn_ichi.COLOR_BLUE)

                textbutton _("Purple"):
                    style "hkb_option"
                    xminimum 200
                    xmaximum 200
                    xalign 0.5
                    text_xalign 0.5
                    action Function(jn_ichi._choosePlayerColor, jn_ichi.COLOR_PURPLE)

                textbutton _("Green"):
                    style "hkb_option"
                    xminimum 200
                    xmaximum 200
                    xalign 0.5
                    text_xalign 0.5
                    action Function(jn_ichi._choosePlayerColor, jn_ichi.COLOR_GREEN)

                null height 8

    else:
        vbox:
            xpos 1052
            ypos 402
            spacing 8

            key "1" action Function(jn_ichi._playSelected)
            key "2" action Function(jn_ichi._playerDrawOrPass)
            key "3" action Function(jn_ichi._requestForfeit)

            textbutton _("Play"):
                style "hkb_option"
                xminimum 200
                xmaximum 200
                text_xalign 0.5
                action Function(jn_ichi._playSelected)
                sensitive _ichi_can_play_selected

            textbutton "[_ichi_draw_button_label]":
                style "hkb_option"
                xminimum 200
                xmaximum 200
                text_xalign 0.5
                action Function(jn_ichi._playerDrawOrPass)
                sensitive _ichi_can_draw_or_pass

            textbutton _("Forfeit"):
                style "hkb_option"
                xminimum 200
                xmaximum 200
                text_xalign 0.5
                action Function(jn_ichi._requestForfeit)
                sensitive _ichi_can_forfeit

    for _player_loop in range(_ichi_player_hand_count):
        $ _idx = (_ichi_player_hand_count - 1) - _player_loop
        $ _card_x = _ichi_player_hand_right_x - (_idx * _ichi_player_hand_step)

        if jn_ichi._selected_index == _idx:
            imagebutton:
                idle jn_ichi._getScaledCardDisplayable(jn_ichi._player_hand[_idx]["path"])
                hover jn_ichi._getScaledCardDisplayable(jn_ichi._player_hand[_idx]["path"])
                action Function(jn_ichi._setSelectedIndex, _idx)
                hovered Function(jn_ichi._setHoveredIndex, _idx)
                unhovered Function(jn_ichi._clearHoveredIndex)
                hover_sound gui.hover_sound
                activate_sound gui.activate_sound
                xpos _card_x
                ypos _ichi_player_hand_y
                at ichi_hand_card_selected
                sensitive jn_ichi._canPlayerSelectCard(_idx)

        elif jn_ichi._hovered_index == _idx:
            imagebutton:
                idle jn_ichi._getScaledCardDisplayable(jn_ichi._player_hand[_idx]["path"])
                hover jn_ichi._getScaledCardDisplayable(jn_ichi._player_hand[_idx]["path"])
                action Function(jn_ichi._setSelectedIndex, _idx)
                hovered Function(jn_ichi._setHoveredIndex, _idx)
                unhovered Function(jn_ichi._clearHoveredIndex)
                hover_sound gui.hover_sound
                activate_sound gui.activate_sound
                xpos _card_x
                ypos _ichi_player_hand_y
                at ichi_hand_card_hover
                sensitive jn_ichi._canPlayerSelectCard(_idx)

        else:
            imagebutton:
                idle jn_ichi._getScaledCardDisplayable(jn_ichi._player_hand[_idx]["path"])
                hover jn_ichi._getScaledCardDisplayable(jn_ichi._player_hand[_idx]["path"])
                action Function(jn_ichi._setSelectedIndex, _idx)
                hovered Function(jn_ichi._setHoveredIndex, _idx)
                unhovered Function(jn_ichi._clearHoveredIndex)
                hover_sound gui.hover_sound
                activate_sound gui.activate_sound
                xpos _card_x
                ypos _ichi_player_hand_y
                at ichi_hand_card
                sensitive jn_ichi._canPlayerSelectCard(_idx)

init 5 python:
    registerTopic(
        Topic(
            persistent._topic_database,
            label="talk_play_ichi",
            unlocked=True,
            prompt="Do you want to play Ichi?",
            conditional="persistent.jn_snap_unlocked",
            category=["Games"],
            player_says=True,
            affinity_range=(jn_affinity.HAPPY, None),
            location="classroom"
        ),
        topic_group=TOPIC_TYPE_NORMAL
    )

label talk_play_ichi:
    $ _ichi_affinity_tier = jn_ichi._getAffinityDialogueTier()

    if _ichi_affinity_tier == "love":
        $ _ichi_ask_line = renpy.substitute(random.choice([
            "Of course I do, [jn_utils.getRandomTease()]. Come here.",
            "You want Ichi? Yeah. I was kind of hoping you'd ask.",
            "Ichi with you? Mhm. That sounds perfect.",
            "When you ask like that? Yeah. Let's play."
        ]))
        show natsuki 1nwmbs at jn_center

    elif _ichi_affinity_tier == "enamored":
        $ _ichi_ask_line = renpy.substitute(random.choice([
            "Ichi? Sure thing, [player]!",
            "Ehehe. Let's go.",
            "Ichi? Yeah. I'm in.",
            "You wanna play Ichi with me? Let's do it."
        ]))
        show natsuki 1uwrsm at jn_center

    elif _ichi_affinity_tier == "affectionate":
        $ _ichi_ask_line = renpy.substitute(random.choice([
            "Well, yeah. Obviously!",
            "Ichi with you? Sure.",
            "You want Ichi? Heh. Fine by me.",
            "Yeah, of course I do."
        ]))
        show natsuki 1uchsm at jn_center

    else:
        $ _ichi_ask_line = renpy.substitute(random.choice([
            "You wanna play Ichi? Sure!",
            "Ichi? Yeah, obviously!",
            "You picked Ichi? Good choice.",
            "Oh? Ichi? Yeah, let's do it."
        ]))
        show natsuki 1nchsm at jn_center

    n "[_ichi_ask_line]"

    if Natsuki.getDeskItemReferenceName(jn_desk_items.JNDeskSlots.right) == "jn_card_pack":
        $ _ichi_desk_line = renpy.substitute(random.choice([
            "Good thing I still had the cards out, huh?",
            "Heh. Saved me a trip. The cards are already out.",
            "Nice. The cards were already right here.",
            "Good. One less thing to set up."
        ]))
        show natsuki 1fchsm at jn_center
        n 1fchsm "[_ichi_desk_line]"

    else:
        $ _ichi_setup_line = renpy.substitute(random.choice([
            "Let me just get set up real quick...",
            "Hang on a sec. Let me get the cards out...",
            "One second. I need to get us set up...",
            "Hold on. Lemme get everything ready..."
        ]))
        show natsuki 3unmaj at jn_center
        n 3unmaj "[_ichi_setup_line]"

        show natsuki 4fcssm
        show black zorder JN_BLACK_ZORDER with Dissolve(0.5)
        $ jnPause(1.5)
        play audio drawer
        $ Natsuki.setDeskItem(jn_desk_items.getDeskItem("jn_card_pack"))
        show natsuki 4fchsm
        hide black with Dissolve(1)

    jump ichi_intro

label ichi_intro:
    $ _ichi_intro_line = renpy.substitute(random.choice([
        "Alright! Let's play some Ichi!",
        "Alright! Ichi time.",
        "Okay! Let's get a game going.",
        "Heh. Alright. Let's do this."
    ]))
    show natsuki 4uchsm at jn_center
    n 4uchsm "[_ichi_intro_line]"

    show natsuki 6uwlsm at jn_center
    menu:
        n "You need a quick rules rundown first, or are you good?"

        "Yeah, let's go over it.":
            jump ichi_explanation

        "I'm good. Let's play!":
            $ _ichi_confident_block = jn_ichi._chooseDialogueBlock([
                [("2fcssm", "Heh."), ("4fsqbg", "Confident already, huh?"), ("4fchgn", "Great! Because so am I.")],
                [("2fcssm", "Oh?"), ("4fchbg", "Skipping the rules and jumping straight in?"), ("4fsqsm", "Good. Then don't embarrass yourself.")],
                [("2fchsm", "Ehehe."), ("4fsqbg", "You sound pretty sure of yourself already."), ("4fchgn", "Nice. That'll make this more fun.")]
            ])

            $ _ichi_expr = "natsuki " + _ichi_confident_block[0][0]
            $ _ichi_line = _ichi_confident_block[0][1]
            show expression _ichi_expr at jn_center as natsuki
            n "[_ichi_line]"

            $ _ichi_expr = "natsuki " + _ichi_confident_block[1][0]
            $ _ichi_line = _ichi_confident_block[1][1]
            show expression _ichi_expr at jn_center as natsuki
            n "[_ichi_line]"

            $ _ichi_expr = "natsuki " + _ichi_confident_block[2][0]
            $ _ichi_line = _ichi_confident_block[2][1]
            show expression _ichi_expr at jn_center as natsuki
            n "[_ichi_line]"

            jump ichi_start

        "Thanks, [n_name]. I'll play later.":
            $ _ichi_later_pick = random.randint(1, 3)

            if _ichi_later_pick == 1:
                show natsuki 2nslpo at jn_center
                n 2nslpo "Really?"
                show natsuki 4nllfl at jn_center
                n 4nllfl "Well... fine."
                show natsuki 2flrpo at jn_center
                n 2flrpo "...Spoilsport."

            elif _ichi_later_pick == 2:
                show natsuki 2ccsem at jn_center
                n 2ccsem "Seriously?"
                show natsuki 4cnmfr at jn_center
                n 4cnmfr "You ask to play and then bail?"
                show natsuki 2fcssm at jn_center
                n 2fcssm "Hmph. Fine. I'll hold you to it later."

            else:
                show natsuki 2nslpo at jn_center
                n 2nslpo "Aww... already?"
                show natsuki 4fsqpo at jn_center
                n 4fsqpo "You're really gonna leave me hanging like that?"
                show natsuki 2fcssm at jn_center
                n 2fcssm "Whatever. I'm not forgetting you promised."

            jump ichi_put_away_and_return

label ichi_explanation:
    hide screen ichi_tutorial_cards
    show natsuki 4unmaj at jn_center

    $ _ichi_rules_start = renpy.substitute(random.choice([
        "Okay. Pay close attention.",
        "Alright, let's cover the basics.",
        "Oh, you're gonna love this.",
        "Great! Here's the rundown."
    ]))
    n 4unmsm "[_ichi_rules_start]"
    n 3tnmss "We both start with seven cards."
    n 4tnmsm "And then there's one card face-up in the discard pile."
    n 4nnmss "The cards come in four colors: pink, blue, purple, and green."
    n 6fwrbg "No points for guessing why I chose those. Ehehe."
    n 3uchsm "When it's your turn, you try to match the card in the discard pile by color. Or symbol."
    n 4tnmss "So if the top card is pink, then you play pink."
    n 3unmaj "But let's say it's a pink 5. Instead of a pink, you can just play a 5 of any color."
    n 6nchbl "Because besides the color, it's identical. Get it?"
    n 4fsqsm "So, if that card's a pink 5, and you have a bunch of green cards you want to get rid of..."
    n 3unmbo "And one of those green cards is a 5..."
    n 6nwrlg "Then playing that 5 changes the color and can totally throw your opponent off their game."

    show natsuki 3uwrsm at jn_left
    menu:
        n "You following me so far?"

        "Makes sense.":
            show natsuki 4nlrbg at jn_center
            n 4nlrbg "Great. Then let's keep going."

        "Hmm. Go over that again?":
            show natsuki 2nchsm at jn_center
            n 2nchsm "No problem."
            jump ichi_explanation

    n 6ulrsm "Same idea for the cards that aren't just a number. The symbol cards I mentioned."
    n 6nchbg "Let's call those {i}action cards."

    show natsuki 4fsqsm at jn_left

    show screen ichi_tutorial_cards([
        jn_ichi.ASSET_ROOT + "/pink_stop.png"
    ])
    n 7ulrsm "This one's {i}Stop{/i}."
    n 4nchsm "In a two-player game like this, it skips the other player and gives you another turn."

    show screen ichi_tutorial_cards([
        jn_ichi.ASSET_ROOT + "/pink_stop.png",
        jn_ichi.ASSET_ROOT + "/pink_reverse.png"
    ])
    n 7nlrbg "This is {i}Reverse{/i}."
    n 7uupaj "Normally it flips the order around..."
    n 6nwmbg "But with only two players, it works the same as Stop."
    n 4fwrbg "So yeah. Another extra turn card. We'll both get used to a lot of that."

    show screen ichi_tutorial_cards([
        jn_ichi.ASSET_ROOT + "/pink_stop.png",
        jn_ichi.ASSET_ROOT + "/pink_reverse.png",
        jn_ichi.ASSET_ROOT + "/pink_draw_two.png"
    ])
    n 7tlrbs "This one's {i}Draw Two{/i}."
    n 7ctrbg "The other player spends their turn drawing two cards..."
    n 6fchsm "And then it's your turn again. Good for you."

    show screen ichi_tutorial_cards([
        jn_ichi.ASSET_ROOT + "/pink_stop.png",
        jn_ichi.ASSET_ROOT + "/pink_reverse.png",
        jn_ichi.ASSET_ROOT + "/pink_draw_two.png",
        jn_ichi.ASSET_ROOT + "/wild.png"
    ])
    n 7clrsg "{i}Wild{/i} is easy."
    n 2nchbg "You play it, then pick whatever color you want."
    n 3nwrss "So if the current color is blue and you pick pink..."
    n 4fcsbg "Then the next card has to match pink instead."
    n 2nchbg "If your opponent's on a streak... Well, maybe now they're not."

    show screen ichi_tutorial_cards([
        jn_ichi.ASSET_ROOT + "/pink_stop.png",
        jn_ichi.ASSET_ROOT + "/pink_reverse.png",
        jn_ichi.ASSET_ROOT + "/pink_draw_two.png",
        jn_ichi.ASSET_ROOT + "/wild.png",
        jn_ichi.ASSET_ROOT + "/wild_draw_four.png"
    ])
    n 7flrlg "I saved the best for last. This menace is called {i}Wild Draw Four{/i}."
    n 4fsgbg "It's a Wild and two Draw Two cards at the same time."
    n 3fchbs "It does a lot with a little, packs a wallop, and is full of surprises."
    n 7csqsm "Remind you of anyone?"
    n 6twdaj "Buuuut there's one small catch."
    n 2tsqfs "You can't just {i}decide{/i} you're playing it whenever you feel like it."
    n 6ktrsm "Whatever the current color is, you can't have that in your hand."
    n 6cchbg "Surprising? Everyone forgets that part. Maybe try reading the rules, it's printed right there."
    n 3cnmsm "So you'll wanna save it for when it'll really mess up your opponent."
    n 3cchgn "Look forward to seeing a {i}lot{/i} of this card."
    n 3fsqsg "From my side of the table."

    hide screen ichi_tutorial_cards
    show natsuki 7tllss at jn_center

    n 7tllss "Basically that's it. One last thing though."
    n 4tnmss "If you {i}can{/i} play a card, you {i}have{/i} to."
    n 4nchsm "If you {i}can't{/i}, you can draw one instead."
    n 6nchdv "But when you draw, you {i}have{/i} to play that new card... if you can."
    n 6tslsm "If you're really scheming, you can risk a draw on purpose."
    n 7nsqsg "It'll probably backfire. But I'm not gonna stop you."
    n 3fchbg "And that's it. First one to dump their whole hand wins."
    n 6fwlbg "...Which is gonna be me, obviously."

    show natsuki option_wait_smug at jn_center
    menu:
        n "Got it?"

        "Got it! Let's play.":
            show natsuki 4fcsbg at jn_center
            n 4fcsbg "Great!"
            n 4fchgn "Good luck. You're gonna need it."
            jump ichi_start

        "I think I'm still confused.":
            $ _ichi_affinity_tier = jn_ichi._getAffinityDialogueTier()

            if _ichi_affinity_tier == "love":
                $ _ichi_repeat_block = jn_ichi._chooseDialogueBlock([
                    [("7nwmsm", "Unnnh... still fuzzy, huh, [player]?"),
                     ("4unmaj", "Alright. I'll walk you through it again from the top.")],
                    [("7nwmsm", "Heh. Guess I crammed a lot in at once."),
                     ("4unmaj", "Deep breath. We'll do a slower rerun, just us two.")],
                    [("7nwmsm", "Okay, okay. That's on me."),
                     ("4unmaj", "I'll break it down nice and slow, so you don't have to stress about it.")],
                    [("7nwmsm", "Alright. One more time."),
                     ("4unmaj", "Step by step from the beginning. If it's still weird, we'll fix it together.")]
                ])

            elif _ichi_affinity_tier == "enamored":
                $ _ichi_repeat_block = jn_ichi._chooseDialogueBlock([
                    [("7ntlsm", "Alright, [player]. Guess we're doing a rerun."),
                     ("4unmaj", "I'll take it from the top again, so try keeping up this time.")],
                    [("7ntlsm", "Wow. That fast, huh?"),
                     ("4unmaj", "Okay. Reset. I'm going through it again, and you're staying with me this time, got it?")],
                    [("7ntlsm", "Heh. Still confused, huh? Figures."),
                     ("4unmaj", "Fine. I'll slow it down a notch so even you can't pretend you missed it.")],
                    [("7ntlsm", "Okay, okay. Again."),
                     ("4unmaj", "Full run-through from the start. Pay close attention.")]
                ])

            elif _ichi_affinity_tier == "affectionate":
                $ _ichi_repeat_block = jn_ichi._chooseDialogueBlock([
                    [("7ntlsm", "Alright, alright. Rewind."),
                     ("4unmaj", "I'll start over. Try not to let it fly straight out of your head this time, dummy.")],
                    [("7ntlsm", "Man, you really do like the easy mode, huh?"),
                     ("4unmaj", "Okay. One more pass, nice and simple so your brain doesn't melt.")],
                    [("7ntlsm", "Still not clicking? Of course."),
                     ("4unmaj", "Fine. I'll explain it slower. But I'm not spoon-feeding you forever, got it?")],
                    [("7ntlsm", "Alright, dummy. Round two."),
                     ("4unmaj", "Back to the beginning. Don't drift off.")]
                ])

            else:
                $ _ichi_repeat_block = jn_ichi._chooseDialogueBlock([
                    [("7ntlsm", "You're still confused? Seriously?"),
                     ("4unmaj", "Fine. I'll go from the top again, but you better be paying attention this time.")],
                    [("7ntlsm", "Ugh. Of course you are."),
                     ("4unmaj", "Let's just do another quick run-through so we can move on already.")],
                    [("7ntlsm", "Okay, okay, I get it."),
                     ("4unmaj", "I'll break it down again, but I'm not dumbing it down forever.")],
                    [("7ntlsm", "Sure. One more time."),
                     ("4unmaj", "Listen up. I'm starting over, so don't waste it by spacing out.")]
                ])

            $ _ichi_repeat_expr = "natsuki " + _ichi_repeat_block[0][0]
            $ _ichi_repeat_line = renpy.substitute(_ichi_repeat_block[0][1])
            show expression _ichi_repeat_expr at jn_center as natsuki
            n "[_ichi_repeat_line]"

            $ _ichi_repeat_expr = "natsuki " + _ichi_repeat_block[1][0]
            $ _ichi_repeat_line = renpy.substitute(_ichi_repeat_block[1][1])
            show expression _ichi_repeat_expr at jn_center as natsuki
            n "[_ichi_repeat_line]"
            jump ichi_explanation

        "Thanks, [n_name]. I'll play later.":
            $ _ichi_explain_backout_pick = random.randint(1, 3)

            if _ichi_explain_backout_pick == 1:
                show natsuki 2ccsemesi at jn_center
                n 2ccsemesi "..."
                show natsuki 2ccsem at jn_center
                n 2ccsem "Seriously?"
                show natsuki 4cnmfr at jn_center
                n 4cnmfr "I went through all that and now you're backing out?"
                show natsuki 4fcssm at jn_center
                n 4fcssm "Hmph. Fine. Your loss."

            elif _ichi_explain_backout_pick == 2:
                show natsuki 2ccsemesi at jn_center
                n 2ccsemesi "..."
                show natsuki 2nslpo at jn_center
                n 2nslpo "Wow. Really?"
                show natsuki 4fsqpo at jn_center
                n 4fsqpo "You made me explain the whole game and now you just bail?"
                show natsuki 2fcssm at jn_center
                n 2fcssm "Tch. Unbelievable. Guess it really didn't sound fun to you, huh?"

            else:
                show natsuki 2ccsemesi at jn_center
                n 2ccsemesi "..."
                show natsuki 2ccsem at jn_center
                n 2ccsem "You cannot be serious."
                show natsuki 4nllfl at jn_center
                n 4nllfl "I just did the full rundown for you."
                show natsuki 2flrpo at jn_center
                n 2flrpo "Hmph. Well, remember that for next time, I guess."

            jump ichi_put_away_and_return

label ichi_start:
    # Enter gameplay mode.
    # Hide the regular hotkey overlay and flag Natsuki as in-game so
    # normal conversation/input systems do not compete with the minigame UI.
    $ HKBHideButtons()
    $ Natsuki.setInGame(True)

    show black zorder JN_BLACK_ZORDER with Dissolve(0.35)
    play audio card_shuffle
    $ jn_ichi._setup()
    $ jnPause(0.85)

    # The vanilla right-desk card pack is drawn over Natsuki's sprite.
    # Clear it before gameplay so it cannot cover her hand.
    if Natsuki.getDeskItemReferenceName(jn_desk_items.JNDeskSlots.right) == "jn_card_pack":
        $ Natsuki.clearDeskItem(jn_desk_items.JNDeskSlots.right)

    show natsuki 1uchsm at jn_left
    show screen ichi_table_hand
    show screen ichi_ui
    hide black with Dissolve(1.00)
    $ jnPause(0.15)

    $ _ichi_coinflip_line = renpy.substitute(random.choice([
        "Let's see who goes first...",
        "Now let's see who starts...",
        "Time to see who gets first move...",
        "Alright. Let's see who opens."
    ]))
    show natsuki 1unmaj at jn_left
    n 1unmaj "[_ichi_coinflip_line]"

    play audio coin_flip
    show natsuki 1tnmbo at jn_left
    n 1tnmbo "..."

    $ _ichi_affinity_tier = jn_ichi._getAffinityDialogueTier()

    if jn_ichi._is_player_turn:
        if _ichi_affinity_tier == "love":
            $ _ichi_player_first_b = renpy.substitute(random.choice([
                "Heh. Look at you getting first move.",
                "Okay, you start. I wanna see your best shot.",
                "Go on, [player]. Make me proud.",
                "Mm. You first. I like seeing you think."
            ]))

        elif _ichi_affinity_tier == "enamored":
            $ _ichi_player_first_b = renpy.substitute(random.choice([
                "Fine. Don't waste it, [player].",
                "You got first move? Then make it count.",
                "Lucky. Now show me it wasn't a fluke.",
                "Well, look who got lucky."
            ]))

        elif _ichi_affinity_tier == "affectionate":
            $ _ichi_player_first_b = renpy.substitute(random.choice([
                "Tch. A head start. Don't waste it!",
                "You got first move, so make it count, okay?",
                "Well look who's lucky. Don't mess it up!",
                "Let's see if you can use that head start."
            ]))

        else:
            $ _ichi_player_first_b = renpy.substitute(random.choice([
                "Going first? Don't waste it.",
                "Try not to blow that head start right away.",
                "First move? Make it count.",
                "You got first move. Do something good with it."
            ]))

        show natsuki 1fsqsm at jn_left
        n 1fsqsm "[_ichi_player_first_b]"

    else:
        if _ichi_affinity_tier == "love":
            $ _ichi_nat_first_c = renpy.substitute(random.choice([
                "Guess I'm starting. Try to keep up, okay?",
                "Me first this time. Don't worry, I'll go easy. Kind of.",
                "I'll open, you follow. We make a good team like that.",
                "Looks like I'm up. Just relax and watch me show off."
            ]))

        elif _ichi_affinity_tier == "enamored":
            $ _ichi_nat_first_c = renpy.substitute(random.choice([
                "Try and keep up, [player].",
                "Ooh, bad luck. I get to start.",
                "Me first. Let's go.",
                "...You'll need all the luck you can get.",
                "I could go easy on you, but... I'm not gonna."
            ]))

        elif _ichi_affinity_tier == "affectionate":
            $ _ichi_nat_first_c = renpy.substitute(random.choice([
                "Looks like I'm going first, [player].",
                "Better not fall behind too fast.",
                "Try not to lag behind.",
                "Guess I'm setting the pace here."
            ]))

        else:
            $ _ichi_nat_first_c = renpy.substitute(random.choice([
                "Try and keep up, [player].",
                "Keep up, okay?",
                "Don't fall behind already.",
                "Try not to lag behind."
            ]))

        show natsuki 1uchsm at jn_left
        n 1uchsm "[_ichi_nat_first_c]"

    if jn_ichi._is_player_turn:
        show natsuki 1nwmsm at jn_left

    else:
        show natsuki snap at jn_left

    $ jn_ichi._controls_enabled = True

    jump ichi_main_loop

label ichi_main_loop:
    # Main runtime loop for the minigame.
    # Keep gameplay screen visibility and Natsuki's in-game state in sync,
    # then process end-state, reshuffle chatter, queued quips, AI turns,
    # or player input availability in that order.
    if not renpy.get_screen("ichi_table_hand"):
        show screen ichi_table_hand

    if not renpy.get_screen("ichi_ui"):
        show screen ichi_ui

    if not Natsuki.isInGame():
        $ Natsuki.setInGame(True)

    if jn_ichi._game_state is not None:
        jump ichi_end

    $ jn_ichi._checkDeckThresholds()

    if jn_ichi._pending_reshuffle:
        call ichi_deck_reshuffle
        jump ichi_main_loop

    elif len(jn_ichi._queued_quips) > 0:
        $ jn_ichi._controls_enabled = False
        call ichi_show_quips
        jump ichi_main_loop

    elif not jn_ichi._is_player_turn:
        $ jn_ichi._controls_enabled = False

        # Reuse Snap's built-in thinking animation while Natsuki is deciding.
        show natsuki snap at jn_left

        $ jnPause(delay=random.uniform(0.45, 0.85), hard=True)
        $ jn_ichi._takeAITurn()
        jump ichi_main_loop

    else:
        $ jn_ichi._controls_enabled = True

        # Return to a normal gameplay idle whenever control is back to the player.
        show natsuki 1nwmsm at jn_left

        $ renpy.pause(0.10)
        jump ichi_main_loop

label ichi_show_quips:
    # Drain queued gameplay chatter one line at a time.
    # The sprite is shown manually here so gameplay quips can stay decoupled
    # from the card-resolution python functions that queued them.
    while len(jn_ichi._queued_quips) > 0:
        python:
            _ichi_exp, _ichi_line = jn_ichi._queued_quips.pop(0)
            renpy.show(
                "natsuki {0}".format(_ichi_exp),
                at_list=[store.jn_left],
                zorder=store.JN_NATSUKI_ZORDER
            )

        n "[_ichi_line]"
        show natsuki 1uchsm at jn_left

    return

label ichi_deck_reshuffle:
    $ jn_ichi._controls_enabled = False

    $ _ichi_affinity_tier = jn_ichi._getAffinityDialogueTier()

    if _ichi_affinity_tier == "love":
        $ _ichi_reshuffle_block = jn_ichi._chooseDialogueBlock([
            [("1unmaj", "Alright. Hold on a second."), ("1fcssm", "We burned through the deck, so I'm reshuffling.")],
            [("1nchsm", "Okay. Quick pause."), ("1uchsm", "I'm resetting the deck. Then we're getting right back to it.")]
        ])

    elif _ichi_affinity_tier == "enamored":
        $ _ichi_reshuffle_block = jn_ichi._chooseDialogueBlock([
            [("1unmaj", "Alright. Hang on."), ("1fcssm", "Deck's out. I'm reshuffling.")],
            [("1nchsm", "Welp. There it goes."), ("1fsqsm", "Give me a second to reset the deck.")]
        ])

    elif _ichi_affinity_tier == "affectionate":
        $ _ichi_reshuffle_block = jn_ichi._chooseDialogueBlock([
            [("1unmaj", "Alright. Give me a sec."), ("1fcssm", "Deck ran dry, so I'm reshuffling.")],
            [("1nchsm", "Okay. Pause."), ("1fsqsm", "I'm resetting the deck. Don't go anywhere.")]
        ])

    else:
        $ _ichi_reshuffle_block = jn_ichi._chooseDialogueBlock([
            [("1unmaj", "Hold on."), ("1fcssm", "Deck's empty. I'm reshuffling.")],
            [("1nchsm", "Okay. Pause."), ("1fsqsm", "Give me a second to reset the deck.")]
        ])

    $ _ichi_reshuffle_expr = "natsuki " + jn_ichi._toSittingExpression(_ichi_reshuffle_block[0][0])
    $ _ichi_reshuffle_line = renpy.substitute(_ichi_reshuffle_block[0][1])
    show expression _ichi_reshuffle_expr at jn_left as natsuki
    n "[_ichi_reshuffle_line]"

    $ _ichi_reshuffle_expr = "natsuki " + jn_ichi._toSittingExpression(_ichi_reshuffle_block[1][0])
    $ _ichi_reshuffle_line = renpy.substitute(_ichi_reshuffle_block[1][1])
    show expression _ichi_reshuffle_expr at jn_left as natsuki
    n "[_ichi_reshuffle_line]"

    show black zorder JN_BLACK_ZORDER with Dissolve(0.35)
    play audio card_shuffle
    $ jnPause(0.85)
    $ jn_ichi._performDeckReshuffle()
    hide black with Dissolve(0.65)

    show natsuki 1nwmsm at jn_left
    return

label ichi_put_away_and_return:
    show natsuki 1nwmsm at jn_center
    show black zorder JN_BLACK_ZORDER with Dissolve(0.5)
    $ jnPause(1.0)
    play audio drawer

    if not Natsuki.getDeskSlotClear(jn_desk_items.JNDeskSlots.right):
        $ Natsuki.clearDeskItem(jn_desk_items.JNDeskSlots.right)

    $ jnPause(1.25)
    $ jn_ichi._cleanupAfterGame()
    show natsuki 1uchsm at jn_center
    hide black with Dissolve(1.0)
    return

label ichi_end:
    hide screen ichi_ui
    hide screen ichi_table_hand
    $ jn_ichi._controls_enabled = False
    show natsuki 1uchsm at jn_center
    $ _ichi_affinity_tier = jn_ichi._getAffinityDialogueTier()

    if jn_ichi._game_state == jn_ichi.JNIchiStates.player_win:
        n 1ccsfl "Nnnnn...!"
        n 1fsqpo "Seriously?"
        n 1csqfl "You actually won that one?"
        n 1nslpo "..."
        n 1fsqsm "Fine."
        n 1fcsbg "Enjoy it while it lasts, [player]."

        $ play_again_prompt = renpy.substitute(random.choice([
            "...Again. Let's do it again.",
            "One more!",
            "Wanna run that back?",
            "I demand a rematch!"
        ]))

    else:
        $ _ichi_win_block = jn_ichi._chooseDialogueBlock([
            [("1fchbg", "Yes!"), ("4fcsbg", "And {i}that's{/i} how you play Ichi, [player]."), ("1fchsm", "Well. I hope you learned something.")],
            [("1fchbg", "Ehehe. There we go!"), ("4fcsbg", "Looks like I still got it."), ("1fchsm", "Try not to be so crushed, okay?")],
            [("1fchbg", "Heh. Knew it."), ("4fcsbg", "Told you I had this."), ("1fchsm", "Not bad, though. You kept up better than I expected.")],
            [("1fchbg", "Gotcha!"), ("4fcsbg", "You made me work for it, but I still won."), ("1fchsm", "Don't worry. Maybe you can still get me next round.")]
        ])

        $ _ichi_win_expr = "natsuki " + _ichi_win_block[0][0]
        $ _ichi_win_line = renpy.substitute(_ichi_win_block[0][1])
        show expression _ichi_win_expr at jn_center as natsuki
        n "[_ichi_win_line]"

        $ _ichi_win_expr = "natsuki " + _ichi_win_block[1][0]
        $ _ichi_win_line = renpy.substitute(_ichi_win_block[1][1])
        show expression _ichi_win_expr at jn_center as natsuki
        n "[_ichi_win_line]"

        $ _ichi_win_expr = "natsuki " + _ichi_win_block[2][0]
        $ _ichi_win_line = renpy.substitute(_ichi_win_block[2][1])
        show expression _ichi_win_expr at jn_center as natsuki
        n "[_ichi_win_line]"

        $ play_again_prompt = renpy.substitute(random.choice([
            "Again?",
            "Another round?",
            "Wanna go again?",
            "One more?"
        ]))

    $ Natsuki.calculatedAffinityGain()

    show natsuki 1fchbg at jn_center
    menu:
        n "[play_again_prompt]"

        "You're on.":
            if jn_ichi._game_state == jn_ichi.JNIchiStates.player_win:
                if _ichi_affinity_tier == "love":
                    $ _ichi_again_line = renpy.substitute(random.choice([
                        "Heh. Of course you are. Let's do another.",
                        "Okay. Show me it wasn't just a lucky streak.",
                        "Alright, rematch. I wanna see that again.",
                        "Good. I'm not done watching you win yet."
                    ]))
                elif _ichi_affinity_tier == "enamored":
                    $ _ichi_again_line = renpy.substitute(random.choice([
                        "Good. Run it back, [player].",
                        "Then prove that wasn't luck.",
                        "Okay. Do it again, then.",
                        "Fine. Let's see you pull that off twice."
                    ]))
                elif _ichi_affinity_tier == "affectionate":
                    $ _ichi_again_line = renpy.substitute(random.choice([
                        "Good. Run it back.",
                        "Then prove that wasn't luck.",
                        "Okay. Do it again, then.",
                        "Fine. One more, if you think you can."
                    ]))
                else:
                    $ _ichi_again_line = renpy.substitute(random.choice([
                        "C'mon. Run it back.",
                        "Yeah? Then prove that wasn't luck.",
                        "Good. Let's see you do it twice.",
                        "Fine. Again."
                    ]))

            else:
                $ _ichi_again_line = renpy.substitute(random.choice([
                    "Good. Shuffle up.",
                    "Let's reset. I'm not done yet.",
                    "Nice. I was hoping you'd say that.",
                    "Good. Let's go."
                ]))

            show natsuki 1fcsbg at jn_center
            n 1fcsbg "[_ichi_again_line]"
            jump ichi_start

        "I'll pass.":
            if jn_ichi._game_state == jn_ichi.JNIchiStates.player_win:
                $ _ichi_stop_block = jn_ichi._chooseDialogueBlock([
                    [("2fchsm", "Ehehe. Alright."), ("1uchsm", "Thanks for playing with me, [player].")],
                    [("2fchsm", "Heh. Fair enough."), ("1uchsm", "That was fun. We'll do a rematch later.")],
                    [("2nchsm", "Okay, okay."), ("1fchsm", "Good game. You did pretty well, you know.")],
                    [("2uchsm", "Sure. We can stop here."), ("1fchsm", "Thanks for the game, [player].")]
                ])

                $ _ichi_stop_expr = "natsuki " + _ichi_stop_block[0][0]
                $ _ichi_stop_line = renpy.substitute(_ichi_stop_block[0][1])
                show expression _ichi_stop_expr at jn_center as natsuki
                n "[_ichi_stop_line]"

                $ _ichi_stop_expr = "natsuki " + _ichi_stop_block[1][0]
                $ _ichi_stop_line = renpy.substitute(_ichi_stop_block[1][1])
                show expression _ichi_stop_expr at jn_center as natsuki
                n "[_ichi_stop_line]"

            else:
                $ _ichi_stop_block = jn_ichi._chooseDialogueBlock([
                    [("2nwlsm", "Ehehe. Alright."), ("6uchsm", "Thanks for playing, [player].")],
                    [("2nwmbg", "Heh. Alright."), ("6uchbs", "That was fun. Thanks for playing.")],
                    [("2nchsm", "Okay. Fine."), ("2nwmss", "Good game. Let's do it again sometime.")],
                    [("2nwmbg", "Sure. Alright."), ("2nwmss", "Thanks for the game, [player].")]
                ])

                $ _ichi_stop_expr = "natsuki " + _ichi_stop_block[0][0]
                $ _ichi_stop_line = renpy.substitute(_ichi_stop_block[0][1])
                show expression _ichi_stop_expr at jn_center as natsuki
                n "[_ichi_stop_line]"

                $ _ichi_stop_expr = "natsuki " + _ichi_stop_block[1][0]
                $ _ichi_stop_line = renpy.substitute(_ichi_stop_block[1][1])
                show expression _ichi_stop_expr at jn_center as natsuki
                n "[_ichi_stop_line]"

            jump ichi_put_away_and_return

label ichi_forfeit:
    $ jn_ichi._controls_enabled = False

    hide screen ichi_ui
    hide screen ichi_table_hand

    show natsuki 1csqca at jn_left

    menu:
        n "What? Giving up already, [player]?"

        "Yeah, sorry. I give up.":
            $ _ichi_forfeit_pick = random.randint(1, 3)

            if _ichi_forfeit_pick == 1:
                show natsuki 1csqsm at jn_center
                n 1csqsm "Hmph."
                show natsuki 6uchsm at jn_center
                n 6uchsm "Okay! That one's mine, then."

            elif _ichi_forfeit_pick == 2:
                show natsuki 2fsqsm at jn_center
                n 2fsqsm "Wow. You're actually folding on me?"
                show natsuki 4fchbg at jn_center
                n 4fchbg "Fine by me. I'll take the win."

            else:
                show natsuki 2nslpo at jn_center
                n 2nslpo "Already?"
                show natsuki 4fsqsm at jn_center
                n 4fsqsm "Tch. Then I'm counting that as my game."

            jump ichi_put_away_and_return

        "In your dreams.":
            $ _ichi_forfeit_cancel_pick = random.randint(1, 3)

            if _ichi_forfeit_cancel_pick == 1:
                show natsuki 1fchbg at jn_left
                n 1fchbg "That's more like it."
                show natsuki 6uchsm at jn_left
                n 6uchsm "Then make your move already!"

            elif _ichi_forfeit_cancel_pick == 2:
                show natsuki 1fsqsm at jn_left
                n 1fsqsm "Heh. Good answer."
                show natsuki 4fchbg at jn_left
                n 4fchbg "Now quit stalling and play."

            else:
                show natsuki 1uchsm at jn_left
                n 1uchsm "Better."
                show natsuki 4fsqsm at jn_left
                n 4fsqsm "C'mon. I'm still waiting on your move."

            show screen ichi_table_hand
            show screen ichi_ui
            $ jn_ichi._controls_enabled = True
            jump ichi_main_loop