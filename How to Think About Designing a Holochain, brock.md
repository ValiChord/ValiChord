How to Think About Designing a Holochain App:
A Step-by-Step Guide

The idea of this article is to offer a process to walk through when designing a Holochain app. We already have a lot of great technical documentation on how to actually write/build an app once designed, as well as on how to understand Holochain generally. But we still have a gap in materials to help you plan what you’re going to build, how to best frame your approach.

This guide is a process that has been refined over the course of the 25 or so hackathons I’ve been a part of – and used at many of those hackathons, so if you’ve been to one, this may sound familiar. But this post is to ensure you have access to this process without coming to one of our events.

The primary audience for this article is (1) developers considering building a Holochain app. But I’ve also tried to make the language available to (2) non-developers who want to understand some of the Holochain design thinking as well – perhaps because it’s simply of interest, or maybe because they’re considering from a business standpoint whether Holochain could be useful for their needs. If you’re a less technically inclined reader, you may want to skip over some of the more technical sections to absorb the larger patterns.

We’ll take a brief moment to paint the lay of the land, then we’ll jump in to the step-by-step.



The Lay of the Land

Let’s start with some general definitions of terms to lay a foundation for understanding how Holochain works:

    Hash: A cryptographic hash acts as a fingerprint to uniquely identify a data element. Holochain uses a Secure Hashing Algorithm known as SHA-256, so each hash is 256 bits long, and also serves as the address to find and retrieve that data element.

    Hash Chain: A way of linking data together over time using a chain of headers. Each header contains the hash of the previous header and the hash of the newly added piece of data. By containing the hashes of the new entry and the previous header, the data is knit together in a time sequenced chain. Chaining the data in this way prevents any changes to past data once a header has been shared, because the slightest change to any past data would cause a cascade of changes to all following hashes, such that they no longer match the headers previously shared. Each user of a Holochain app has their own personal hash chain, called their Source Chain, where all data they author gets written.

    Hash Table: Data is organized into a key-value lookup table for rapid retrieval using each data element’s hash as a lookup key.

    Distributed Hash Table (DHT): A hash table designed to operate across many computers so that no single one needs to hold the complete set of data, instead there’s a reliable method for knowing which computers are responsible for holding which hashes. Any data intended to be part of the shared state of your Holochain application is replicated to that app’s DHT after a user writes it to their Source Chain. This approach enables changes to take place and be stored locally but looked up globally.


Now, building on those concepts, let’s have a look at how Holochain apps function. [improve this transition to reflect the fact that more definitions are about to ensue, just Holochain-specific ones ]

dApp / micro-service: Each Holochain application provides – or can simply be thought of as – a distinct, P2P-encrypted network and address space. When installing and running an app, the user’s device declares its address on that app’s network and begins interacting with the other peers running the same application code, known as DNA. 

DNA & Zomes: A Holochain app, also called a hApp or DNA, is the particular set of code that every user (or node) that is running that app … 

Note: in common usage, the term DNA is sometimes used interchangeably with hApp, dApp, and app. For the purpose of this article, however, we’ll understand DNA to refer specifically to… back end … single DNA (vs bundle) … etc


Entries: A complete unit of data on a source chain or in the DHT is called an entry. An entry is a bundle which includes content plus context. The content is the new data itself, created in accordance with the data structure rules, known as a schema, specified for that entry type in the app’s DNA. The context is the source chain header which tells you who published the content, as well as the data type of the entry, the author’s signature as proof that it came from them, and their timestamp showing when they created it. 

Links: Links define a relationship between two entries in the DHT, so that you can find an unknown entry (target) by information attached to a known entry (base). Links provide a system of metadata that effectively upgrades Holochain’s DHT from just a key-value store to a graph database. For example, you could retrieve my tweets or the usernames of my followers when they are linked from my username. It’s similar to how links on a web page link you from particular text on a page to other resources on the Internet you may not have known how to find. 


Links are a system of metadata that define relationships between two entries in the DHT, so that an entry can be easily found by information attached to another. For example, using my username (one entry) in a Twitter-like app, you could retrieve my posts or the usernames of my followers (other entries). It’s not unlike how links on a web page connect the text on the source page to content on the destination page. 


Validation Rules: Other nodes use the DNA to validate changes published to the DHT, making sure the entries are structured correctly and also that they follow whatever rules have been set regarding who can do what and how. For example, the validation rules might ensure that you must be the original author of a social media post to edit or delete it. Business logic, permissions, constraints.


Local Data Storage: Each node in an app holds two levels of data storage:

     The user’s private source chain where users write changes that they’ve authored. Each new entry on this chain must be signed by the user’s private key to prove they authored it. In addition to the user-authored entries, eachThe very first entry of every user’s source chain containsis the DNA (application code) to ensure everyone is operating by the same rules, as well as the user’s. The second entry is where each user publishes their public key as their address on that app’s network. 

    “Public” entries written to a source chain get published to the app’s DHT which is the shared space for validating and looking up data. Each node holds their portion (or shard) of the total application data -- specifically they hold the data associated with the hashes that are “near” their address.
    A portion, or ‘shard’shard, or portion, of the application’s DHT, the shared space for validating and looking up data. Specifically, each user holds the the data associated with the hashes that are ‘near’ their address. Data that is meant to be ‘public’, or shared, gets published automatically to the DHT after being committed to a source chain.


Certain data may be private, meaning that it lives only on the author’s individual source chain, while other data is public in that it is automatically published to the DHT after being committed to a source chain.

Capabilities / Security: Holochain uses a cryptographic variant of capabilities tokens for managing all security and permissions. You grant permissions by writing a private entry (a capabilities grant) which specifies what functions can be called by what users (identified by their keys). The hash of that private entry becomes the “key” to unlock those permissions when a request is signed by someone whose public key is authorized in the grant. For example, the second entry in each user’s source chain is a capabilities grant which gives the author permission to write new entries to the chain and sign all network communications. Capabilities can also be used to grant remote users special access to private data or function calls, as well as specify API bridges to other Holochain apps.

For more information on the concepts we just covered and many more, check outMost of these terms and many more are covered in the glossary and the API documentation on the developer site.

Step 0: Make sure Holochain is the right framework for your app

Before going too far in designing your app on Holochain, it’s worth considering whether to do so, since Holochain is decidedly optimized for certain kinds of applications more than others.

CommonThe core use cases for Holochain are apps that are participatory in the sense that they involve user-contributed data. It’s especially ideal whenever users might have a preference for owning their data, managing access to their data, or controlling their identity. Additionally, it can be useful if your key business objective is infrastructure cost savings, resilience to offline/online inconsistency in an environment or if you are wanting to avoid processing of personal data. If your intention is to create a central repository where you have sole control over the system and the data within it, you’re barking up the wrong tree with Holochain.

Also, like most distributed computing systems, Holochain is designed for eventual consistency, as opposed to immediate consensus or true real-time performance. It actually can operate pretty close to real-time, especially as compared to blockchain – we’re talking seconds instead of minutes or hours. But if you need true real-time responsiveness, like for remote surgery or something like that, Holochain isn’t for you.

Lastly – and this one is less a litmus test and more of a key orienting principle – don’t plan to build token-based currencies on Holochain. It’s not impossible, but it neutralizes the main reason to build on Holochain in the first place, which is to avoid the need for global consensus (which an inventory of tokens requires). Instead, think of currencies implemented with Holochain as being account-centric rather than token-centric, with the state of the main events being interactions between agents rather than the updating a global stateof tokens and global states, and you’ll be well-positioned to take advantage of Holochain’s properties for speed and scale.

Key questions:

    Is your app participatory and user-centric in nature, or do you need centralized control over data?

    Can you frame your problem and solution to accommodate eventual consistency, or do you need true real-time performance?

    Can you approach app design with an agent or account-centric versus token-centric mindset?



Step 1. Define your app’s membranes

A membrane, at least as we talk about it in the Holochain world, is a boundary that defines the flow of information or collaboration. By way of a familiar example from the centralized world: a set of membranes exists around your bank account information such that only certain types of users – yourself and various banking staff – can see it. A different, more restricted set of membranes exist around the ability to change that data. There are also membranes that define who may contact you through your banking platform.

The need to define membranes is important for all application development, but it’s especially pertinent when designing a hAppHolochain app because Holochain makes it so easy to create bridges between apps, which is to say ways for apps to share information with one another. Again by way of analogy: if your banking app and your social media apps had the technical capability of bridging to one another’s data, it may be necessary to preventrestrict flows of your banking data to your social circles.

In fact, one way to think about a Holochain app’s very nature is that it governs a set of data in such a way that the data maintains its integrity while also being held by a random set of users that you may not even know. In this way, access to the app itself – who gets to join it at all – is the first membrane to consider and define, since each app creates an encrypted P2P network within which users can interact with each other. The way for a user to get through the app’s membrane is to have their address, their public key, validated by their peers running that app. This could involve an invitation code, a joining fee, a proof of work, or no requirements at all other than announcing their address. Once their address has been validated, a user can exchange messages with the other nodes as well as read and store data which has been published to the app’s shared DHT. 

Thus, if it’s important to create spaces of data that are distinct from one another, you may actually want to create multiple DNAsdistinct apps… even if you intend that these ‘microservices’, this bundle of DNAs, be composed into a single overall hApp with a bundle of DNAsservice, and/or accessed by the same UI(s). Bridging makes it easy to access data across apps, to the extent that’s permitted by each app’s membranes, so creating so there may be little downside to creating distinct DNAs, and there can be real upsides in terms of creating different private spacesapps.

(Note that we’re only talking about shared data, the data published to the DHT, when we talk about the need for membranes. That’s different from data that a user may choose to store privately on their own source chain, which they can selectively make available for viewing by others.)

For example: Let’s explore how you might structure a say you envision a comprehensive service for the management of personal medical data system as three different apps that work together. 

    An individualYou couldmight runcreate one app for the storage of a variety of her personal medical data and diet or exercise logs. She could invite other trusted parties (family or friends) to run a copy of the her personal app so her data would replicate to those other nodes, and could potentially be shared by those friends if there was a medical emergency or if Alice was unconscious.  data by the individuals – (the ‘patients’, I suppose) –, that would also give patients the ability to invite ‘trusted persons’ to their private data space so that they could be helpful in case of medical emergency. along with whoever they might declare as their ‘trusted persons’, such as their immediate families. 

    You might have another app for physician’s practices management, in which doctors and their staffs are able to securely store and access the medical histories of hundreds of patients. 

    A third app could beAnd you could even have a sharing app which allows patients and doctors to send one another encrypted data while never storing any data on that app’s DHT, just keeping a record of that the datathe hash of the bundle of data was shared between the parties.

Those would be three distinct apps with three distinct membranes, each with different shared DHTs or public data spaces. The bridges between the sharing app and each of the storage apps [does something].



Key questions:

What information in your app will be kept private? What information will be shared/public?

What will be theare your boundaries that definefor users’ sharing of data with each other? Can everything be bundled together into one shared DHT, or do you need to create segmented spacessegment off other spaces for data thatwhich is not meant to be visible to everyone?


Key coding concepts: [Later]


Note: Each user can always store private entries to their own source chain which are not published to the DHT. This allows them to selectively give permission for viewing private data. DHTs are for shared data, so we’re talking about membranes between different spaces of shared data.

just an example of that would be like private channels in a slack app could be their own little mini channel app. and then you could invite only the people you want to participate in that channel, you could kick people out of the channel… it functions as a private space, just like a holochain app can function as a private space. and you might have to have an invitation code to join that app, and that shows that you were invited to that public channel. so, we could do this kind of stuff all over the place.

another more clear example would be like personal medical data app where you run a little data logger, a personal data store app, and you have a copy on your laptop or your phone, and your little holoport at home, and your mom or your wife have copies or something like that, because you want somebody other than you to have copies in case you’re unconscious and you need to have somebody share your medical data. and then it automatically is backing up among these nodes and that kind of thing so you have some resilience and that kind of thing but it’s only self-hosted. it’s only held by people you trust: yourself, your mom, your wife, etc. 

and that’s one thing. but then you have this medical marketplace app -- marketplace may be the wrong terminology but bear with me for a moment -- where you interface with health care providers to receive data and/or share data. and the only thing that is recorded in that marketplace is never the medical data itself, but the act of sending and receiving. so that there’s a log that you’ve gotten your records from this hospital or that you shared your records from this doctor. now on the other side of his endpoint of the marketplace app, he’s bridged to a practice management app, where the doctors in his practice can access health records that they’ve gotten shared with them. 

so this is a reason to have very different membranes. the membranes of trust within the practice management app are different than membranes in the data marketplace/sharing place, and then different within your personal data store. each one of those could be an app, and you bridge between the marketplace to bridge from moving the data and just record the act of sharing it (and any agreements about the terms of sharing), and that’s a really good example of membranes -- why certain things would have to be private and certain things would have to be public.

the data is transmitted as a node-to-node message… it’s never shared inside the app, it’s never stored in that DHT. and all communications are encrypted so that’s an encrypted node-to-node message… you do that because you don’t want to store your medical data in a public place, but you may want to have notarized-by-other-nodes record of something, an acknowledged record by other nodes of something being shared, and then you might have recourse if, you know, you share some data that’s supposed to be anonymized for a study and they leak, you know, non-anonymized data or whatever, and you have a record that it was shared under these conditions and they broke those conditions, it’s basically just a record of the agreements about data sharing. 

one other thing about membranes: i think holochain apps want to be microservices that you pull together and compose together. and that you should keep the functionality within a holochain app and remember apps - holocdhain apps - are about distributed data integrity. the UI is loosely coupled to the app. it’s not really even a part of the holochain part of the app. the UI just like with hylo where we just converted an existing react website with graphQL api, we just put a graphQL shim on top of holochain and we’re just making the calls they used to make to postpress to holochain instead of postpress. so the front end code is like almost all the same, there’s almost no modifications - just a couple tweaks we have to make. but the idea is that that’s not really to do with holochain… that’s a UI and that would be UI no matter what database was running the back end. the advantage of holochain is to have it be decentralized, actually completely peer to peer, and to have you own your own data and to have you control your identity and that kind of thing.

and so the point about microservices is that even for this hilo app, it turns out it’s gonna be about 5 or 6 different apps. there’s the events app and the projects app and the comments and the posts and the member directory - like there’s these different things, and they actually… it would enable the ability to add more apps in… as things that you could connect into the system as you might want to add more features… and if you just have the community app be a thin shim that doesn’t change much then all community members can always talk to each other - you don’t to worry about updates and all that kind of stuff - you can bridge to new apps that introduce new features. cause remember - updating distributing software is hard. updating centralized is easy cause you update it in one place and everyone automatically accesses the update. in distributed software you have to get everybody to update. and so the more you break things into small parts that are unlikely to change, then the less those things have to be updated - the more stable they are for continuing to have everybody interact with one another
2: Plan Your App’s Modules - Composable re-use of your code

Modules are components of your app code that are composed so as to be easily reused or accessed as somewhat standalone phenomena. The intended reuser/accessor might be the app itself, or some sister microservice that’s composed to be part of the same overall service. Or it might other be other, less related apps entirely, which is how apps within the Holochain ecosystem can so easily share code with one another and avoid reinventing the wheel each time.

In fact, it’s likely that at some point apps will be able to reference modules ‘on the fly’ at an address or hash, such that modules don’t even need to be packaged in the first place.

Still, while fairly simple, it’s a non-trivial undertaking to modularize code. So it’s worth considering which parts, if any, should be made into modules.

Key questions:

    What are the parts of your app that you may need to reuse or abstract into other contexts?

    How might parts of your code need to be reused?

    What parts might be separable from one another?


The answers to these questions are often not black and white. instead being left to the discretion of the developers, or at least the best guesses about what might be most useful in the future.

For example:

Key coding concepts:

within one of these apps what are the parts that you may need to reuse or abstract into separate things. like if you build an app that is for indexing other apps, you have a little mix-in module that you just drop in that knows how to talk to your indexing app. and that lets you have a little bit of stuff you can mix in to an app to bridge over to the indexing app where only indexing nodes participate in the indexing app. the nodes that have volunteered to index all the data in the whole system, for example.

so that’s an example of why you might want modules.

there’s other reasons that you might want code reuse. modules are kind of the lowest level of composability within holochain and are manifest when you install apps will probably be able to reference modules at an address / URL / particular hash and be able to install that module on the fly, so that you don’t even have to package all the modules in your code if you’re reusing a module that someone else is supplying.

a lot of times people want to know how they should modularize their code and that’s a somewhat difficult and arbitrary question. how might it need to be reused? what parts might be separable from each other? there’s a lot of different ways that can go - there’s not always one answer to that question.
3. Define Your Entry Schemas - Data structures, schemas, and CRUD

Entries, as we noted earlier, are the units of data that users publish to their source chains and, in some cases, to the DHT. Different apps have entirely different types of data that make up entries, ranging from [...] to [...] to [...]. So it’s important to consider what precisely constitutes an entry for your app, including its structure, the …, and its schemas, the ... .

Entries are the core atomic units of data integrity on Holochain. We call them entries because each one is an entry in a larger cryptographic structure (either a hash chain or DHT). You might think of the structure of an entry like the fields you might define in a database table, except that entries are not stored in relational tables, but rather are inserted as entries in your source chain, then replicated to other hosts to hold in their DHT store so your shared data is always available to the app, even when you’re offline.

The structure of each entry is confirmed against the schema, which is the … for the … defined/contained within the DNA. Each entry is then hashed and signed to prevent alteration. 

Process: Also, the structure of each entry is confirmed, and each is hashed and signed to prevent alteration. Finally, the validation rules associated with the entry type ensures the author had appropriate permission and was in an appropriate state to commit that entry. 

If you’ve worked with a key-value store or document database (like MongoDB, Redis, DynamoDB, or Firebase/Firestore, how to define, store, and retrieve data form Holochain’s data systems may be familiar to you. 

Name the Entry Type: 

Define your data schema. A data entry can contain multiple fields. You must define which ones are possible, which are required, what data types they are, and any range / value validation required on the data. 

The schema will take the form of a Rust struct in compiled DNA code. On the front-end it would describe what labels and possibly what UI widgets a user might interact with. In the middleware GraphQL layer it will define query structures and linking relationships. We are working on some Rapid App Development (RAD) tools to help you generate front and back-end elements just by specifying the middle layer in GraphQL.

For example, you might define a UserProfile entry tomight contain FirstName, LastName, UserName, and ProfilePic.

Guidelines: 

    Headers already contain important data: Every entry also has an associated header from its author’s source chain. The header contains a timestamp, entry type identifier, hash of the entry, the author’s cryptographic signature, and the author’s address. So you don’t need to put a timestamp inside the entry to know when it was created, nor author info to know who created it.

    Uniqueness of hash keys: Keep in mind that your entry will be retrieved by a key which is simply the hash of the contents of the entry. There are times you may want to put the author, timestamp, or other content to differentiate it from content someone else might publish. For example, my tweet saying “It’s a beautiful morning!” probably shouldn’t collide in the DHT with someone else saying the same thing. Likewise, me saying it again 5 years later, should clearly be a different instance. In this case, you might want to add author and timestamp inside the entry contents to differentiate those tweets.


Define the data structure

What are the different fields that this table holds

Defining what data is stored in an entry

How that’s structure and what is required to validate it - that’s sort of a later step but the basic is the structure, the schema. 


Key questions:

For example: Use the Tweet example with timestamp and such?

Key coding concepts:

Create read update delete functions for these entries

You could think of this kind of like the database tables. But it’s like what are the database structures that you’re operating with, and what’s their structure, what’s their schemas, and, eventually, what’s their validation rules, like what makes that valid data or not, and who can make changes to it as often in the CRUD rules - that’s the next part of design that you do.

and i’m gonna skip over too much detail here. and i think that’s kind of the high-level thing.

they’re called entries because they’re an entry in your chain and they’re an entry in the DHT - they’re an entry in a cryptographic structure of some sort. each record is sort of an independent record so these work a little more like mongoDB or an object data store or document data store as opposed to a relational table. 

If a Tweet has a timestamp and a body, for example, in the entry… it also has a header which contains the timestamp, but you don’t want me Tweeting good morning to collide with yours… 58:00 on 5.13 for more

4. Define the Links Between DHT Entries

The next thing to define is the ways thathow entries relate to one another, known as links. One way you could think of links is that they’re similar to how you might define relationships in a relational database, -- where one kind of data connects in with another to make it easier to query. Links turn the Holochain DHT from a key-value store into a graph database, by establishing connections that can be followed from one entry to others.

For example, you might have the entry for a chat channel – which might include (name, description, and type (such as pub/priv) –) link to all the entries for chats typed into that channel. You might look up the source (author) of a chat and follow a link from their address to their profile to display their username and avatar/image.

But in Holochain you would want to use links even more than relationships in a database, because you will need them to find and retrieve data in the DHT. In a relational database, you have allALL the data in one place, so you can index it, or iterate through every record to find something. But in a DHT, you have an impossibly large search space spread across many machines. There’s really no good way to crawl through all the data in that space, and there’s no global index of content (unless you build one into your app). This means if you just create an entry and throw it into the DHT without creating a link as a kind of breadcrumb to find your way back to it, then chances are nobody else will be able to find or use your data.

Let’s return to the example ofImagine a Ttwitter application built on Holochain. If my tweet just gets pushed to the DHT, and you want to view my Ttwitter feed, how are you going to find my tweets? If I’m was online, you could ask me to send a list of all my tweets,  (which I can easily find on my source chain). If I’m was offline and headers are published to the DHT, you could go to my public key address, and follow links to the headers of my chain entries, and reconstruct my chain to search it for all my tweets. But that’s a lot of work and lookups of data that are notNOT tweets.

A better approach would be to attach links tagged as “tweet” to an entry for my handle or username that you know. Then in one single DHT command you could getlinks on my handle, returning all links that are tagged “tweet.” Or you could get links tagged “follower” to find my followers. Links make finding data on the DHT much easier.

So, bottom line: think about how you are going to want to find and retrieve your entries from the DHT, and be sure you put links in place to complete those queries.

Key questions:

For example:

Key coding concepts:

GetLINKS / Load:True

and then the next thing is the links or relationships between these things - the entries - because you implicitly/explicitly? link one thing to another. and this doesn’t happen at the abstract table level, this happens at the individual entry level. so if for example - joshmzemel - if that’s your user name in a holochain-based twitter, then that may be set up as an anchor where people can find you by your username and follow links to find your posts or your followers or who you’re following…

you can attach to that links to your followers or your tweets or favorites… which allows me to collect that data in a whole distributed-data world out there spread across many different machines that allows me to have a place to go to find all those hashes in the DHT, to collect them up. so it’s a kind of graphing database where you can connect parts to other parts.



5. Validation of Entries & Links (warrants?) - Mutual enforcement of fundamental data integrity

And here we get to what, in a real way, is the heart of the whole Holochain system: the fact that data validation can be mutually enforced by an app’s users (or nodes) in a purely peer-to-peer fashion, without the need for a global consensus at any time. Even though users effectively represent their own states, such as account balanc es or other data, the data maintains eventual consistency because the ways that individuals are able to represent data are governed by strict validation rules. And once data is published to an app’s DHT, it cannot be changed.

(I sometimes say that whereas blockchain systems try to enforce what is said – which is problematic in various ways, most notably that it’s hopelessly inefficient – within Holochain it’s how things are said that’s enforced.)

So, it’s up to you to set the specific rules regarding how data may be represented. [more here] Rules need to be written such that they will return a consistent result no matter which nodes are performing the validation, and no matter the order in which the nodes show up to perform the validation. 

In addition, you also need to define ay what happens when there’s a validation fail. [more here] 

Specify structure and value constraints 

Dependent logic 

Spaces and relation to spaces (validation on links)

Building validation packages: Entry+Header, Prior Entry, sub-chain, full-chain

Key questions: 

For example: 

Key coding concepts: entry validation 



Even though it’s the 6th thing in here it’s kind of the heart of the whole system. it’s really what makes holochain holochain is the validation rules, the peer-to-peer, mutually-enforced validation that guarantees data integrity even though people can represent their own account balance or whatever… it’s because they can only do things which follow the rules, and they can’t change things once they’re published… once the hash becomes published to the DHT it becomes immutable… and validation rules is what manages the integrity of all of that. 

and interestingly, you don’t start off by thinking about the validation rules… you start off by building all this other frame around it, but the validation rules are the heart of the data integrity of the system. and they have to be able to be run from any user’s perspective in any order, and typically include whatever proof they need, either in the entry or in their validation package, such that any node can deterministically validate that, so that you don’t have some nodes thinking ‘this is valid’, and other nodes saying ‘no it’s not’, cause one of the things that comes out of this as well is the possibility of warrants, but we’re not gonna talk about that too much right now. but that’s like when things fail to validate, do flag people as fraudulent and how… you create a warrant… when certain types of validation fail. then we know you’re trying to double-spend from your account or whatever.

for example, in clutter, our peer-to-peer twitter, if you look at the validation code, you can see that i can’t edit one of your tweets, cause it checks to make sure it’s being edited by the person who authored it. but the very next line, the next section, is about deleting tweets, and it doesn’t check anything. it just says ‘return true’ - there’s no validation. so i could delete one of your tweets. now the UI doesn’t provide any actual way to do this, but technically, if i wanted to modify/customize the UI, i could send a call to delete one of your tweets. it doesn’t validate that it’s you trying to do it. this is an example of mutually-enforced data integrity - how you can make sure that no one is doing things that they shouldn’t.

another example would be checking your account balance to make sure you have the funds you’re trying to spend. or things like that.

6. Collections - Functions to retrieve and organize collections of entries

Remember, performing updates/upgrades to distributed software is not as easy as updating centralized software, because you have to get everyone to update their local copy to the new version of DNA. Therefore, you want to minimize functionality inside the DNA to only what is required to ensure data integrity. Things that are more likely to change (like graphics, themes, UI, business logic, etc.) should be put into the user- interface part of the system to minimize the need for updating DNA.

By this point, you’ve defined (via entries and links) and constrained (via validation rules) all the ways that data can be created, updated, or deleted. And you should have initially established your membranes and definitions of public/private entries to safely manage who can read content. With all that CRUD handled, what’s left? *(CRUD = Create, Read, Update, & Delete.)

Queries.

Since Holochain’s DHT is a key value store, it is optimized for rapid retrieval of a single piece of data by its key. GetLinks() also makes it pretty easy to retrieve a list of linked entries attached to a single entry. But if you want to perform a more complex query where you may need to follow through multiple layers of links, you could manually handle that inside your app, but you may also want to consider compiling some queries into your holochain app to minimize the data and steps you’ll need to sift through in your UI layer.

Even mMore importantly, if you have very large collections of data, you may need to employ some specific strategies for managing the links so you don’t create crazy “hot spots” in the DHT where certain nodes have to carry a huge burden because you linked, say, 2 billion social network user profiles from a single entry. How unfair would it be to the few nodes keeping that huge user directory up to date and servicing everyone’s queries for users.

Structuring Queries:

Structuring Large Collections: 



Key questions:

For example:

Key coding concepts:

and structuring your relationships and links in your app is the next step. links are also typically how you will collect collections of stuff. i said posts in the plural linked off of your username, or followers in the plural, right, that’s usually how you will go and find a collection of things as you collect links up from a base entry.

7. UX / UI - Choose your favorite framework to connect to your dApp calls

In this case, I put UX and UI design at the end of the story because it is very loosely coupled with the data integrity management of the Holochain DNA. It can evolve separately, or not be connected at all, and the DNA marches on with its self-healing and balancing of the network. However, you could just as easily start with UX/UI to shape the requirements of your application. There certainly many use cases that would benefit from this kind of more user-centric approach.

We figure that for most user-facing apps, that only about 10% of your dev energy should go into steps 1  through 6, and 90% of your energy will go into step 7 to make it look good and make sense to users. Also, we expect that the UI is where you are likely to need to make the most frequent changes, which is why the UI is not part of the app DNA. You can roll out new versions of UI as frequently as you want without people having to update their DNA. As long as you don’t affect the mutually enforced rules about data integrity, the DNA can remain the same.

You can also freely choose what tools or code frameworks to use. There’s no reason you can’t use Vue, Angular, React for a browser based UI, or something like QT for a desktop widget UI, or whatever you like to develop in.

GraphQL / middleware

and then lastly we have the UX/UI which is all very loosely coupled and can connect to multiple apps. you can integrate multiple DNAs or back ends with one front end. so the microservices architecture again figures in here as loosely coupled. 

Conclusion / Wrap-up

Distribution options

Nod to upcoming article about how to solve problems that may be challenging for eventual consistency & P2P




NOTES/OUTTAKES


2 topics that may be two different articles

1. how do you even go through the process of designing a Holochain app? that’s the part that there’s this dev camp video that’s been recorded

what lens do you look through and what are the steps you go through to design a holochain app

we have a lot of writing and documentation about writing and building holochain apps

but not a lot at the design thinking level

documentarians so far have been more nuts and bolts -- how to plug x into y, vs how to plan what you’re building

this one is probably the lower-hanging fruit

one recorded session quickly

2. more important in terms of unique value that art has to bring (vs above which a few people on team could handle): 

what are the design patterns, what are sort of winning patterns where you probably wouldn’t have thought of this without a lot of work or trial or whatever… kind of pro tips… don’t bang like that, try this…

that’s really the article i’m talking about

but it goes hand in hand with the first article - here’s the approach to designing a holochain app

this is the juicier article

pro tips… how to solve various kinds of problems... and reference the design process 

i think we called this one the ‘cook book’ but that term could probably apply to the other too

we could come up with the first handful very quickly

but if we want to go deeper it’s going to require more processing and thought, possibly by art between sessions to sketch out some things

why these articles?

we’re entering into a phase where we need to have people building apps

and we’re getting to a point where holochain rust is mature enough for people to do that

the truth is that a lot of our developers are not practical users of holochain

they don’t think in these patterns

there’s not necessarily another good person to write this

there’s something from both being the architect

as well as having facilitated 23 hackathons

that has art be in a particular position to write this

worked with hundreds of different people trying to use these patterns

you shouldn’t have to come to one of our hackathons to get this information

but it’s not likely to come out of our developer documentation


    Membranes - Boundaries of membership, privacy, and collaboration

    Modules - Composable re-use of your code

    Entries - Data structures, schemas, and CRUD

    Links - Defining relationships between DHT entries 

    Collections - Functions to retrieve and organize collections of entries

    Validation Entries & Links (warrants?) - Mutual enforcement of fundamental data integrity

    UX / UI - Choose your favorite framework to connect to your dApp calls


add ‘key questions’ to each section

and what about a single example running throughout? a hypothetical case.

how to introduce/contextualize this sequence?

what examples to add to the sequence to give it color?

do we want to include code snippets with examples?

is this THE design thinking or Art’s suggested design thinking?

step 0 - is this optimized for holochain apps

first let’s talk about how holochain works

but actually this is probably in the tips and tricks

thinking about eventual consistency

how to make the cookbook accessible

about 1:20 on 4.30

Note from Art: instead of code snippets, we may want to add to each of the sections some Key Concepts bullets which spell out basically what commands or structures you use in Holochain to embody the design concepts described.

Josh: sure. could also - if we do want to include some code - include it as graphics/screenshots so as not to take up the whole width and intimidate less technical readers too much. but that still could be problematic in becoming out of date.

===

so, for me, this is the basic design process, design sequence of what you walk through, the kind of thinking or modeling you walk through when designing a holochain app.

this is not a technical instruction manual for designing apps so much as a conceptual here’s the sequence/process you should go through.

here’s the things you should think about and an order to think about them

links and relationships section: might make a mention of anchors

design patterns that work

but this here’s just the basic process

here’s how to think about designing an app

the documentation is much lower-level

i’ve done this at pretty much every hackathon

what we just talked about is the abstraction

and in each case there should be examples

and potentially example code

i think we need to give the abstraction a general example

and then maybe throw code blocks in, or link to them

another id

Secondarily, could also be cool if some of the (only) somewhat technically minded people asking the business question of can I use holochain for this, how would I approach using holochain for this, if it could also serve them

===

might have to also say what holochain is good for and what it is not

don’t try to build this on holochain - stick with building this kind of thing on holochain

it’s optimized for these types of things and not these other types of things

kind of like a step 0: is this project appropriate for holochain

the things it’s best for is participatory stuff

user-contributed data where users care about owning their data, controlling their identity, that type of thing

if your intention is some central repository where you have sole control over the system and the data and that kind of thing, you’re barking up the wrong tree with holochain.

if you need true real-time performance -- remote surgery or something like that -- don’t use holochain. you can get something real-time ish, especially compared to blockchain in that you don’t have to wait like 10 minutes for commits or that kind of thing, but holochain is designed for eventual consistency. it’s designed for resilience even when messages are not immed in their propagation. so don’t count on messages being immediate.

another thing i would warn away from: 

massive assets at the moment. like people may not be set up to host your 20GB blu-ray dvd file. don’t go dumping your stuff into a DHT where people aren’t expecting to hold massive assets like that. if you’re going to build a video serving platform, then make sure everybody knows that’s what they’re signing up for when they’re installing it.

the last thing: everybody thinks about currency in the blockchain context so they think about tokens, they think about having an inventory of tokens. because of holochain’s agent-centric architecture, you should think of it as interactions between agents, transactions between agents, and it’s an account-centric reference not a token-centric frame of reference. don’t think about it as tokens; think about it as accounts that are controlled by agents and you’ll be approaching currency correctly to take advantage of the speed and scaling properties of holochain.

validating interactions

more if needed at 1:00:00

one other contextual thing -- actually this will be for the design thinking article 

see 46:45 on recording when ready

=====


Each app or DNA creates an encrypted P2P network for users to interact with each other. The first step into the membrane of an app is to have your address (public key) validated by your peers running that app. This may involve an invitation code, a joining fee, a proof of work, or no requirements at all other than announcing your address. Once your address has been validated, you can send and receive messages to the other nodes as well as read and store data which has been published to the shared DHT. You should relate to any data published to the shared DHT as public to all members of the app/DNA because even if it isn’t displayed to someone via the UI, they may be able to inspect DHT data they store on their hard drive..

So if you want to create very distinct spaces of data access you may want to create distinct apps. For example, your personal medical data app (which you allow only trusted people to run such as yourself, your spouse, or a parent or child) vs. a practice management app where doctors collect data from multiple patients. You could even have medical data sharing app which allows users of the sharing system to send encrypted data so that you could send or receive data from your doctor’s app, but never store medical data on the sharing app itself. Those would be three distinct apps to produce three distinct membranes.




While the primary audience for this article is developers, I’ve also tried to make some of the design thinking available to non-developers, so that you can understand some of the Holochain design thinking as well – perhaps because you’re interested, or maybe because you’re considering from a business standpoint whether Holochain could be useful for one purpose or another.


Primarily you’ll be interested in this article if you’re considering building a Holochain app. 


this article is intended for people considering building a holochain app

i’m trying to make some of the design thinking accessible to non-developers, but if you’re a developer wanting to build an app, this is definitely for you

our developer docs / API / are great for telling you syntax for commands and the parameters to provide

but not so great at telling you how to frame your approach, including why you would use which commands when. this is intended to be a starting place for that.

might have to also say what holochain is good for and what it is not

don’t try to build this on holochain - stick with building this kind of thing on holochain

it’s optimized for these types of things and not these other types of things

kind of like a step 0: is this project appropriate for holochain

the things it’s best for is participatory stuff

user-contributed data where users care about owning their data, controlling their identity, that type of thing

if your intention is some central repository where you have sole control over the system and the data and that kind of thing, you’re barking up the wrong tree with holochain.

if you need true real-time performance -- remote surgery or something like that -- don’t use holochain. you can get something real-time ish, especially compared to blockchain in that you don’t have to wait like 10 minutes for commits or that kind of thing, but holochain is designed for eventual consistency. it’s designed for resilience even when messages are not immed in their propagation. so don’t count on messages being immediate.

another thing i would warn away from: 

massive assets at the moment. like people may not be set up to host your 20GB blu-ray dvd file. don’t go dumping your stuff into a DHT where people aren’t expecting to hold massive assets like that. if you’re going to build a video serving platform, then make sure everybody knows that’s what they’re signing up for when they’re installing it.

the last thing: everybody thinks about currency in the blockchain context so they think about tokens, they think about having an inventory of tokens. because of holochain’s agent-centric architecture, you should think of it as interactions between agents, transactions between agents, and it’s an account-centric reference not a token-centric frame of reference. don’t think about it as tokens; think about it as accounts that are controlled by agents and you’ll be approaching currency correctly to take advantage of the speed and scaling properties of holochain.

validating interactions

more if needed at 1:00:00

Key questions to ask:

the very first question is ‘who does it include? who does it exclude? are there different boundaries for groups or indivs within the app? are there things that are private? are there things that are public? you need to figure that stuff out from the very outset, and because holochain makes it easy to bridge between apps, that often the case should be that you’re segregating content to different apps that have different DHTs and different sharing spaces. 

