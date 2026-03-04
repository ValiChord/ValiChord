# 🛡️ ValiChord: The 4-DNA Membrane Architecture

## ValiChord is built as a series of independent but connected "bubbles" (technically called DNAs) rather than a single monolithic program. Each bubble has its own membrane—a digital boundary that controls who can join the network and what information is allowed to leave. This ensures that sensitive research data stays private while the "proof" of the science becomes public.

#1Researcher Repository DNA (Private Membrane)

    Function: Runs locally on the researcher's or institution's own computer.

    Role: This is the "home base" that holds the original research—the raw code, secret data, and early notes.

    Privacy: Sensitive information (like private patient records) stays inside this bubble; it never touches the internet or the shared network, making the system GDPR compliant by its very nature.

#2Validator Workspace DNA (Private Membrane)

    Function: An isolated, temporary "locked room" for a single independent validator.

    Role: This is where the actual reproduction attempt (or "Repro Witnessing") happens; the validator re-runs the researcher's code here to see if it produces the same results.

    Privacy: No other validators can see inside this room while the work is happening, which prevents "groupthink" and ensures the validator is not influenced by peers.

#3Attestation DNA (Shared DHT)

    Function: A shared digital bulletin board for credentialed participants.

    Role: Instead of storing the research itself, it records the act of validation—signed statements (attestations) and digital "fingerprints" proving that a check-up occurred.

    Integrity: It manages the commit-reveal protocol, where validators must lock in their findings before they are allowed to see what others found.

#4Governance & Harmony Records DNA (Public DHT)

    Function: A publicly readable library for the whole scientific community.

    Role: Stores the final Harmony Records, badges, and public validation statuses.

    Control: Only the system's official rules can "write" to this library, but anyone—journals, funders, or the public—can "read" it to verify reproducibility signals.

🧠# Plain English Glossary

Technical Term	Brief Explanation or Analogy
ValiChord	A "distributed immune system" for science that verifies if research is actually reproducible.

DNA (Holochain)	The Club Rulebook. In this system, a "DNA" is a specific set of rules that defines a small, private network.

Membrane	The Bouncer. A security boundary that decides who is allowed into a specific network and what data is allowed out.

Shared DHT	A Neighborhood Bulletin Board. A way for people to share information without a central "Big Brother" server; everyone holds a small piece of the board.

Cryptographic Proof	A Digital Fingerprint. A unique code representing a file. If even one comma changes in the file, the fingerprint changes completely.

Commit-Reveal	The Sealed Envelope. You put your answer in an envelope on the table (Commit) and only open it (Reveal) once everyone else has done the same.

Data Locality	Keeping it at Home. Keeping data on your own device rather than sending it to a "Cloud" server owned by a corporation.

Immutable	Carved in Stone. Once information is recorded in the ledger, it can never be changed or deleted.

Tamper-Evident	A Wax Seal. You might not stop someone from trying to change data, but you will immediately see that the "seal" is broken if they try.

Static Analysis	The Proofread. Looking at the files and code to find obvious mistakes without actually running the program.

# For a deeper dive into the technical specifications, see the ValiChord Technical Reference and the Governance Framework.
