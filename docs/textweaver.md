# textweaver

textweaver is a Rust reimplementation of star's core: reading documents aloud with a highlight that follows the spoken word exactly, keyboard-first navigation, and speech feedback while writing. It starts as a self-voicing terminal reader (`textweaver`) and a scripting CLI (`tw`), with a native GUI planned later.

- Repository: https://github.com/leavesofgrass/textweaver
- Implementation plan: https://github.com/leavesofgrass/textweaver/blob/main/docs/plan.md
- What star 0.1.31 does, and the bugs textweaver fixes instead of porting: https://github.com/leavesofgrass/textweaver/blob/main/docs/star-parity.md

star itself is not changing because of this. textweaver's `tw migrate-star` command (planned) will import star's settings, reading positions, and bookmarks.
