Title: "Introducing our new and updated user experience"
Date: 2025-04-27
Summary: You can "just" make a website, y'know

I just completely redesigned the theme for this website. The theme is now crafted from 100% artisanal, hand-written HTML and CSS, so that it no longer looks like every other generic, somewhat-dated [Bootstrap](https://getbootstrap.com/) page.

This was much easier than I thought it would be, especially in this modern era where Internet users generally at least somewhat update their web browsers and thus gain support for new platform features. (_Forced_ updates which restrict user freedoms are a net negative for the software industry, and users should ideally be _allowed to_ run old, outdated, even insecure software if they _intentionally choose_ to. Here I am merely referring to the ease of _delivering_ new software.)

Although new web platform features help, the biggest stumbling blocks personally were about _ways of thinking_, and so I want to try to document some of those.

# How do you lay out text on a page?

No really. When you open a typical current text editor or word processor program, or if you just type words into HTML, what _actually_ happens?

Typically, words get put next to each other in the standard writing direction (i.e. left-to-right, unless you're using a right-to-left language such as Arabic or Hebrew). Once the line fills up, words are moved down to a new, empty line, and the process repeats. This corresponds to the "inline" direction of the standard CSS [flow layout](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_display/Flow_layout), although the exact semantics may differ between the web vs word processors.

However, this is *not* how you lay out components of a _page_! For that, it helps to look at the pre-digital era of _publishing_. Material from this era, such as newspapers and magazines, tended to (at a very high level) be laid out as "blocks" into which text, images, and other content would be placed. (As computers advanced and enabled "desktop publishing" to develop, the shape of these blocks became less restrictive.)

Here is where the first **"key insight"** shows up. Flow layout is fine (sorry, TeX and [hot metal typesetting](https://en.wikipedia.org/wiki/Hot_metal_typesetting) fans) for the step of "just write the words", but it is not enough for laying out a web _page_, which is a _page_, which means it contains elements beyond "just the words" (e.g. headers, footers, navbars).

## Rectangles all the way down

Here's where we encounter a huge limitation with standard CSS flow layout. The "block" direction only goes down. It's very hard to put blocks _next_ to each other. (I first saw this explained this succinctly by [Eevee](https://eev.ee/blog/2020/02/01/old-css-new-css/).)

I've been quite aware of features such as [flexbox](https://css-tricks.com/snippets/css/a-guide-to-flexbox/) and [grid](https://css-tricks.com/snippets/css/complete-guide-grid/) which were supposed to help fix CSS layout woes, but it took way too long to actually put _all_ the ideas together.

These new CSS layout tools allow you to *divide up rectangles into smaller rectangles*. These smaller rectangles can easily go next to each other in addition to the default of above/below each other. On a pre-digital dead-tree page, said page would be subdivided into fixed rectangles. In the modern digital era, the same can be done to the viewport, but now with additional flexibility and dynamism because it is On The Computer. You then put the words you have written _inside of_ these rectangles.

Dividing up space in this way is _not_ just for building "application UIs" but is _also_ important for "just" documents the moment these documents need to be presented in a "nice" way. If anything, the inspiration/causality were likely the other way around! (This is probably one of the consequences of being spicy-brained and having spent way too much time on the computer.)

Viewing page layout in terms of _subdividing rectangles_ might help to explain the wholehearted adoption of using `box-sizing: border-box;` by designers everywhere.

# Seeing the invisible

One thing that I _constantly_ struggled against was that I simply _could not understand_ why any page design I came up with constantly looked "old and ugly" no matter what I tried changing. There are smaller issues which I will discuss later, but it took someone else to finally point out that the biggest thing I had overlooked was literally invisible.

I had been completely failing to see **the spacing between text and blocks**. This includes what in CSS would be called "margin" or "padding" but also features such as line height. Many modern websites have _much_ more empty space between text than default browser settings. Although I am not certain on the causality, I suspect that larger, higher-resolution screens allowed for much more flexibility in this department.

Although it was used in a "positive" way, this idea could be described as _infohazardous_. The instant I was told this piece of information, I suddenly started perceiving the empty spaces everywhere (both on websites and on offline irl media). Something which I had been silently surrounded by my entire life suddenly stood out and made itself known.

(TeX and hot metal typesetting fans, this means I finally see some of what you can see.)

Actually making changes to my website afterwards was still based on vibes, but I am comfortable enough listening to vibes once I have "enough" conscious understanding of how they work.

# Everything else

Browser default fonts and font sizes feel somewhat dated because, well, they're the default. I'm not a huge typography geek, but I do understand it well enough once I was able to disentangle it from the spacing/padding issue. Fixing typography is simple enough with a few lines of CSS.

A very notable sub-feature of browser default styling is the color of hyperlinks. Once again, the defaults have been the defaults for a very long time. However, there are usability arguments for why hyperlinks should remain distinguishable, so on this page I have chosen to keep underlines as well as a hint of the classic blue/purple colors, but they've been tweaked just enough to not feel "ugly" due to datedness.

A number of useful CSS features manage to ship in the past decade. Most notable for my purposes:

* [variables ("custom properties")](https://developer.mozilla.org/en-US/docs/Web/CSS/--*)
* [`calc()`](https://developer.mozilla.org/en-US/docs/Web/CSS/calc)

# An aside on retrotech

This website has a number of "retro" design elements, yet it also embraces quite a few modern ideas.

Even though there are legitimate frustrations fueling reactions such as [the motherfucking website](https://motherfuckingwebsite.com/), _technology should improve over time_! Not only have I been able to make use of newer CSS features and layout strategies, I'm also able to:

* run an editor, a web browser, and a development server *at the same time*
    * on a laptop
    * with the trust that it probably isn't going to crash (even though I do have the "spam `Ctrl+S`" habit of the era)
* debug my web page
    * do you _really_ want to live without modern devtools? even if you _are_ restricting yourself to HTML4+CSS1, that sounds like a frustrating experience
* _not_ have to debug my web page (across browsers and platforms)
    * standardization helps!
* edit images and pixel art with free (as in beer) software
    * which I could download from the internet, without having to think about how long it will take
    * watch _a video_ explaining how to use said software, for free
    * some of this software even nominally respects my freedoms!

I hope I'm picking a good compromise (and not perpetuating the idea that website redesigns are always negative).

