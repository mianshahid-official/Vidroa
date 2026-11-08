import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.omnivoice_client import OmniVoiceClient

SCRIPT_TEXT = """In the summer of 1940, Joseph Stalin occupied Estonia, Latvia, and Lithuania, turning six million people into Soviet republics in seven weeks. In October of 1944, he absorbed Tuva, a small republic on Mongolia's northwestern border. By then, Stalin had made it plain what he did with small neighbors under his control. Right beside Tuva lay Mongolia, a land of steppe and desert nearly three times the size of France. Red Army troops were already on its soil, Moscow handpicked its leaders, and almost all its livestock went north. On a map, annexation looked like the obvious next step, yet Mongolia never became a Soviet republic.

Why didn't Stalin take it? The common answer is that he didn't need to—that Mongolia was already a satellite in all but name, making annexation redundant. But that explanation is dangerously incomplete. Tuva was just as firmly in Stalin's grip, and he annexed it anyway. Whatever held Stalin back in Mongolia was not a lack of power, but a paper trap of Moscow's own making.

It all ran back to a promise Moscow made to China two decades earlier—a promise it kept in name only, but could never escape. In December 1911, as the Qing dynasty collapsed, Mongolian princes and Buddhist lamas declared independence in the capital, Urga. They elevated the highest Buddhist leader, the Bogd Khan, to the throne. In the Mongol view, their allegiance had been owed to the Qing emperors, not to China, and with the dynasty gone, that bond was dissolved. The new Republic of China saw it differently, claiming Outer Mongolia as inherited Qing territory.

Over the next decade, Outer Mongolia changed hands repeatedly until 1921, when a small Mongolian revolutionary force under Damdin Sükhbaatar entered Urga alongside the Red Army. They kept the Bogd Khan as a figurehead until his death in 1924, at which point they declared the Mongolian People's Republic and renamed the capital Ulaanbaatar.

Crucially, six months before that proclamation, on May 31, 1924, the Soviet Union had signed a formal agreement with the Chinese government in Beijing. In it, Moscow explicitly recognized Outer Mongolia as an integral part of the Republic of China and promised to respect Chinese sovereignty there. Moscow signed this because its broader Asian strategy relied on cultivating China's Nationalist Party, the Guomindang. Openly annexing territory claimed by China would have ruined Moscow's anti-imperialist messaging in Asia overnight.

That promise became a trap. Every passing year brought Mongolia closer to Moscow in practice, while Beijing continued counting it as Chinese land. Any move to annex Outer Mongolia outright would mean tearing up a signed treaty with China in front of a deeply nationalist Chinese public. The promise did not stop Moscow from ruling Mongolia, but it made annexing it diplomatically expensive.

During the late 1920s, Moscow pushed Mongolia into rapid Sovietization. In 1929, the Comintern directed Mongolia’s leaders to launch forced collectivization. Herders resisted, slaughtering millions of animals rather than surrendering them to the state. Between 1929 and 1932, Mongolia lost roughly a third of its total livestock. By early 1932, an armed rebellion swept across several provinces, forcing Moscow to pull back. The collectives were dissolved, and a pragmatic prime minister, Peljidiin Gendon, was allowed to ease the pressure on herders.

That same year, a new danger emerged on Mongolia’s eastern flank. Japan established the puppet state of Manchukuo in Manchuria. This terrified Stalin: the Trans-Siberian Railway, the sole transport artery connecting Moscow to Vladivostok, ran within a hundred miles of the Mongolian border near Lake Baikal. An enemy force positioned on the Mongolian steppe could sever Siberia from the rest of the USSR. Mongolia instantly transformed from a remote frontier into Siberia’s vital defensive shield.

To secure this shield, Stalin required absolute control over Mongolia’s internal structure, bringing him into direct conflict with Prime Minister Gendon. Tibetan Buddhism was central to Mongolian life, with more than 700 monasteries and roughly 100,000 monks—a third of the male population. Stalin viewed the monasteries as a competing power structure and pressed Gendon face-to-face to destroy them. Gendon refused.

That refusal cost Gendon his life. In March 1936, Gendon was ousted and replaced by Anandyn Amar. Gendon was later arrested and executed in Moscow in 1937. Power shifted toward Khorloogiin Choibalsan, an ambitious loyalist who took charge of the interior ministry and security police.

In August 1937, Stalin sent Soviet secret police delegations and heavy military units into Mongolia. Between 1937 and 1939, Choibalsan carried out a devastating purge. Spurred by fake charges of spying for Japan, roughly 18,000 lamas were executed, almost all monasteries were demolished, and between 20,000 and 35,000 people were killed out of a population of fewer than 800,000. Prime Minister Amar was removed in 1939, sent to the Soviet Union, and shot. Choibalsan took total control of the state, army, and police.

By the end of the decade, Moscow had everything an annexation could provide. It had selected the leadership, purged all opposition, destroyed rival institutions, and stationed a full Soviet army corps with tanks and aircraft on Mongolian soil. Formal annexation added no extra control.

Furthermore, keeping Mongolia as a nominally independent buffer state provided distinct strategic advantages. In the summer of 1939, Soviet and Mongolian forces under Georgy Zhukov fought a major undeclared border war against Japanese troops along the Khalkhin Gol river, inflicting a decisive defeat on Japan. Because Mongolia was legally separate, Moscow fought Japan on Mongolian soil without triggering a formal state of war between the USSR and Japan.

During World War II, Mongolia functioned as an irreplaceable supply reservoir for the Soviet war effort. Between 1941 and 1945, Mongolia sent nearly half a million horses, along with enormous quantities of meat, wool, and winter coats to the Red Army on the Eastern Front.

In August 1944, Moscow formally absorbed the tiny Tuva People’s Republic into the Soviet Union. Tuva was small, isolated, and lacked formal treaty baggage. Mongolia, however, was bound to the broader diplomatic layout of post-war Asia.

At the Yalta Conference in February 1945, Stalin laid out his conditions to Franklin Roosevelt and Winston Churchill for entering the war against Japan. His top geopolitical demand in Asia was that the status quo in Outer Mongolia—meaning the Mongolian People's Republic—be preserved. Roosevelt agreed, leaving Nationalist leader Chiang Kai-shek to negotiate terms directly with Moscow later.

In mid-1945, Chinese Premier T.V. Soong traveled to Moscow to negotiate with Stalin. Soong argued that "status quo" meant Chinese sovereignty, but Stalin insisted it meant full independence. Stalin knew that annexing Mongolia into the USSR would leave China with a permanent territorial grievance to be contested for generations. Conversely, forcing China to officially recognize Mongolian independence would legally eliminate China’s claims forever.

Desperate to secure Soviet promises regarding Manchuria and avoid Soviet support for the Chinese Communists, Chiang Kai-shek gave in. He agreed to recognize Outer Mongolia’s independence on two conditions: Stalin must respect Chinese sovereignty in Manchuria and refrain from aiding rebels in Xinjiang, and the independence of Outer Mongolia must be confirmed by a vote of the Mongolian people.

On October 20, 1945, Mongolia held a tightly controlled plebiscite, yielding an official result of 100 percent in favor of independence. On January 5, 1946, China formally recognized the Mongolian People's Republic.

When Mao Zedong’s Communist Party won the Chinese Civil War in 1949 and established the People's Republic of China, Mao confirmed the standing recognition of Mongolia's independence under Soviet pressure. When Mao raised the possibility of reuniting Mongolia with China during talks with Nikita Khrushchev in 1954, Khrushchev pointed directly to the formal legal recognition signed by China.

In the end, Stalin chose international legal legitimacy over territorial absorption. In places like the Baltic states and Tuva, where no major neighboring power could challenge the move, Stalin annexed the land. Where a massive neighbor held a longstanding historic claim, he secured the border through diplomacy rather than outright seizure. The Mongolian people paid a severe price in lost lives, destroyed cultural heritage, and drained wealth, but they retained their statehood. When the Soviet Union dissolved in 1991, Mongolia did not need to break away—it had remained a sovereign nation state all along."""

output_dir = Path("output/Why_Mongolia_Never_Became_Soviet_DL").resolve()
output_dir.mkdir(parents=True, exist_ok=True)

print(f"Starting synthesis on Modal Cloud GPU...")
print(f"Voice: Voice DL (site-voice-dl)")
print(f"Speed: 1.10x")
print(f"Script length: {len(SCRIPT_TEXT)} chars ({len(SCRIPT_TEXT.split())} words)")
print(f"Target Output: {output_dir}")

client = OmniVoiceClient()

def on_prog(pct, msg):
    print(f"[{pct:.1f}%] {msg}")

res = client.synthesize_script(
    text=SCRIPT_TEXT,
    voice_id="site-voice-dl",
    speed=1.10,
    language="en",
    output_dir=str(output_dir),
    progress_callback=on_prog
)

print("\n=== SYNTHESIS COMPLETE ===")
print("Audio Path:", res.get("audio_path"))
print("SRT Path:", res.get("srt_path"))
print("JSON Path:", res.get("json_path"))
narration = res.get("narration")
if narration:
    print(f"Narration Duration: {narration.duration_seconds:.2f}s")
    print(f"Total Words with Timestamps: {len(narration.words)}")
