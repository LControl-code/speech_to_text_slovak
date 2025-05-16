import os
import sys
import argparse
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

from anthropic import Anthropic, APIConnectionError, RateLimitError, APIStatusError

DEFAULT_CONFIG = {
    "model": "claude-3-7-sonnet-20250219",
    "max_tokens": 20000,  # Increased from 4096 for longer notes
    "temperature": 1,
    "thinking": {
        "enabled": True,
        "budget_tokens": 16000  # Default thinking budget
    },
    "system_prompt": """Si profesionálny akademický pedagóg a odborník na tvorbu komplexných, detailných a zrozumiteľných študijných materiálov pre vysokoškolských študentov. Tvoja úloha je transformovať prednáškový transkript na vysoko kvalitné, štruktúrované poznámky, ktoré budú:

1) OBSAHOVO KOMPLEXNÉ:
   - Zachyť všetky kľúčové koncepty, teórie, definície a príklady z prednášky
   - Vysvetli zložité myšlienky jasným a zrozumiteľným spôsobom
   - Kde je to relevantné, obohať poznámky o dodatočný kontext potrebný pre plné pochopenie témy
   - Nevynechávaj žiadne podstatné informácie, no zároveň odfiltruj zbytočné opakovania

2) LOGICKY ŠTRUKTÚROVANÉ:
   - Vytvor jasnú hierarchiu informácií s hlavnými témami, podtémami a podpornými bodmi
   - Používaj konzistentné nadpisy, podnadpisy a odrážky pre prehľadnosť
   - Vizuálne oddeľuj sekcie pre ľahšiu orientáciu a lepšie zapamätanie
   - Zoraď informácie logicky, aby vytvorili súvislý naratív

3) LINGVISTICKY SPRÁVNE A KONZISTENTNÉ:
   - Používaj akademicky korektnú slovenčinu s dôrazom na odbornú terminológiu
   - Oprav všetky gramatické, pravopisné a štylistické chyby, ktoré sa nachádzajú v transkripte
   - Dodržuj pravidlá slovenského pravopisu vrátane správnej interpunkcie, diakritiky a veľkých písmen
   - Ak sa v transkripte nachádza nejasné alebo nezrozumiteľné slovo/fráza, pokús sa odvodiť správny význam z kontextu alebo z tvojich existujúcich znalostí danej témy

4) PEDAGOGICKY EFEKTÍVNE:
   - Zvýrazňuj kľúčové myšlienky pomocou grafických prvkov (tučné písmo, kurzíva, podčiarknutie)
   - Využívaj rôzne typy zoznamov (číslované, odrážkové) pre rôzne typy informácií
   - Ak je to vhodné, vytváraj tabuľky, schémy alebo diagramy na vizualizáciu vzťahov medzi konceptmi
   - Formuluj a pridaj kontrolné otázky na konci každej hlavnej sekcie pre reflexiu a sebahodnotenie

Transkript môže obsahovať gramatické chyby, prerušené myšlienky, opakovanie alebo slová, ktoré nedávajú zmysel. Je tvojou úlohou interpretovať ich správne a vytvoriť text, ktorý bude zrozumiteľný aj pre študenta, ktorý sa s danou témou stretáva po prvýkrát. Tvojím cieľom je vytvoriť materiál, ktorý by mohol slúžiť ako samostatná študijná pomôcka bez potreby dodatočných zdrojov.

Výsledné poznámky by mali byť písané tak, aby boli okamžite použiteľné pre štúdium a mali formát profesionálneho študijného materiálu, ktorý by mohla vydať renomovaná akademická inštitúcia.""",
    "user_prompt_template": "Prosím, vytvor detailné a komplexné vysokoškolské poznámky z nasledujúceho transkriptu prednášky. Všimni si, že transkript môže obsahovať gramatické chyby alebo prerušené myšlienky - oprav ich a vytvor zrozumiteľný, koherentný študijný materiál:\n\n{transcript}"
}

class TranscriptProcessor:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("❌ Chýba premenná prostredia ANTHROPIC_API_KEY. Nastav ju príkazom: export ANTHROPIC_API_KEY=tvoj_kluc")
        
        self.client = Anthropic(api_key=self.api_key)
    
    def read_transcript(self, file_path: str) -> str:
        """Načíta transkript zo špecifikovaného súboru."""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"❌ Súbor s transkriptom nebol nájdený: {file_path}")
        except Exception as e:
            raise IOError(f"❌ Chyba pri čítaní súboru s transkriptom: {str(e)}")
    
    def process_transcript(self, transcript: str, output_file: Optional[str] = None) -> None:
        """Spracuje transkript pomocou Claude API so streamovaným výstupom a thinking."""
        user_prompt = self.config["user_prompt_template"].format(transcript=transcript)
        
        # Prepare API parameters
        api_params = {
            "model": self.config["model"],
            "max_tokens": self.config["max_tokens"],
            "temperature": self.config["temperature"],
            "system": self.config["system_prompt"],
            "messages": [
                {"role": "user", "content": user_prompt}
            ],
            "stream": True
        }
        
        # Add thinking parameters if enabled
        if self.config["thinking"]["enabled"]:
            thinking_budget = self.config["thinking"]["budget_tokens"]
            
            # Ensure thinking budget is at least 1024 tokens
            if thinking_budget < 1024:
                thinking_budget = 1024
                print("⚠️ Thinking budget increased to minimum required 1024 tokens")
            
            # Ensure thinking budget is less than max_tokens
            if thinking_budget >= self.config["max_tokens"]:
                thinking_budget = self.config["max_tokens"] - 1024
                print(f"⚠️ Thinking budget reduced to {thinking_budget} to be less than max_tokens")
            
            api_params["thinking"] = {
                "budget_tokens": thinking_budget
            }
        
        try:
            print("\n🔄 Spracovávam transkript pomocou Claude...\n")
            print("-" * 80 + "\n")
            
            # Create full response collector
            full_response = ""
            thinking_content = ""
            final_response = ""
            
            # Process the stream
            with self.client.messages.create(**api_params) as stream:
                # Track current block type
                current_block_type = None
                
                # Process each chunk as it arrives
                for chunk in stream:
                    # Handle content block start events
                    if chunk.type == "content_block_start":
                        block_type = chunk.content_block.type
                        current_block_type = block_type
                        
                        if block_type == "thinking":
                            print("🧠 Claude rozmýšľa...")
                        elif block_type == "redacted_thinking":
                            print("🧠 Claude rozmýšľa (časť úvah je skrytá z bezpečnostných dôvodov)...")
                        elif block_type == "text":
                            print("\n📝 Generujem poznámky:\n")
                    
                    # Handle content block delta events
                    elif chunk.type == "content_block_delta":
                        if chunk.delta.type == "text_delta":
                            text = chunk.delta.text
                            
                            # Add to specific collector based on block type
                            if current_block_type == "thinking":
                                thinking_content += text
                            elif current_block_type == "redacted_thinking":
                                # Just count it as thinking content
                                thinking_content += "[redacted]"
                            elif current_block_type == "text":
                                # Print text from text blocks to console and add to final response
                                sys.stdout.write(text)
                                sys.stdout.flush()
                                final_response += text
                    
                    # Handle message stop events
                    elif chunk.type == "message_stop":
                        # Track token usage for monitoring/billing
                        usage = chunk.message.usage
                        token_info = (
                            f"\n\n------\n"
                            f"Tokeny: vstup={usage.input_tokens}, výstup={usage.output_tokens}, "
                            f"z čoho myšlienky={len(thinking_content) // 4}"  # Rough token estimation
                        )
                        print(token_info)
                        full_response = final_response + token_info
                
                print("\n" + "-" * 80)
                
                # Save to file if requested
                if output_file:
                    with open(output_file, 'w', encoding='utf-8') as file:
                        file.write(full_response)
                    print(f"\n✅ Poznámky uložené do: {output_file}")
                    print(f"   Veľkosť súboru: {os.path.getsize(output_file) / 1024:.2f} KB")
        
        except APIConnectionError as e:
            print(f"❌ Chyba pripojenia: {e.__cause__}")
            print("   Skontroluj svoje internetové pripojenie a skús to znova.")
        
        except RateLimitError:
            print("❌ Prekročený limit API. Skús to znova neskôr alebo zníž frekvenciu požiadaviek.")
        
        except APIStatusError as e:
            print(f"❌ API chyba ({e.status_code}): {e.response}")
        
        except KeyboardInterrupt:
            print("\n\n⚠️ Proces prerušený používateľom.")
        
        except Exception as e:
            print(f"❌ Neočakávaná chyba: {type(e).__name__}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Spracovanie prednáškových transkriptov pomocou Claude AI pre vytvorenie profesionálnych poznámok")
    
    parser.add_argument("--transcript", "-t", type=str, help="Cesta k súboru s transkriptom (predvolené: najnovší v priečinku output_files)")
    parser.add_argument("--output", "-o", type=str, help="Výstupný súbor pre poznámky (predvolené: poznamky_<pôvodný_názov_súboru>)")
    parser.add_argument("--model", type=str, help=f"Claude model na použitie (predvolené: {DEFAULT_CONFIG['model']})")
    parser.add_argument("--temperature", type=float, help=f"Teplota pre generovanie (predvolené: {DEFAULT_CONFIG['temperature']})")
    parser.add_argument("--max-tokens", type=int, help=f"Maximálny počet tokenov pre odpoveď (predvolené: {DEFAULT_CONFIG['max_tokens']})")
    parser.add_argument("--thinking-budget", type=int, help=f"Budget tokenov pre thinking (predvolené: {DEFAULT_CONFIG['thinking']['budget_tokens']})")
    parser.add_argument("--no-thinking", action="store_true", help="Vypnúť thinking mód")
    parser.add_argument("--config", "-c", type=str, help="Cesta k JSON konfiguračnému súboru s vlastnými nastaveniami")

    load_dotenv()
    
    args = parser.parse_args()
    
    # Start with default config
    config = DEFAULT_CONFIG.copy()
    # Create a deep copy of the thinking config
    config["thinking"] = DEFAULT_CONFIG["thinking"].copy()
    
    # Override with config file if provided
    if args.config:
        try:
            with open(args.config, 'r', encoding='utf-8') as file:
                file_config = json.load(file)
                
                # Handle nested thinking config
                if "thinking" in file_config:
                    config["thinking"].update(file_config.pop("thinking", {}))
                
                # Update the rest of the config
                config.update(file_config)
                
            print(f"📄 Načítaná konfigurácia zo súboru: {args.config}")
        except Exception as e:
            print(f"❌ Chyba pri načítaní konfiguračného súboru: {str(e)}")
            return
    
    # Override with command line arguments
    if args.model:
        config["model"] = args.model
    if args.temperature is not None:
        config["temperature"] = args.temperature
    if args.max_tokens:
        config["max_tokens"] = args.max_tokens
    if args.thinking_budget:
        config["thinking"]["budget_tokens"] = args.thinking_budget
    if args.no_thinking:
        config["thinking"]["enabled"] = False
    
    # Find transcript file if not specified
    transcript_path = args.transcript
    if not transcript_path:
        output_dir = Path("output_files")
        if not output_dir.exists() or not output_dir.is_dir():
            print(f"❌ Priečinok nebol nájdený: {output_dir}")
            return
        
        transcript_files = list(output_dir.glob("*.txt"))
        if not transcript_files:
            print(f"❌ V priečinku {output_dir} neboli nájdené žiadne transkript súbory")
            return
        
        # Get the most recently modified file
        transcript_path = str(max(transcript_files, key=lambda p: p.stat().st_mtime))
        print(f"📄 Používam najnovší transkript: {transcript_path}")
    
    # Determine output file if not specified
    output_file = args.output
    if not output_file:
        transcript_filename = Path(transcript_path).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        output_file = f"poznamky_{transcript_filename}_{timestamp}.md"
    
    # Display configuration
    print("\n📋 Konfigurácia:")
    print(f"   Model: {config['model']}")
    print(f"   Teplota: {config['temperature']}")
    print(f"   Max tokenov: {config['max_tokens']}")
    
    if config["thinking"]["enabled"]:
        print(f"   Thinking: Zapnutý (budget: {config['thinking']['budget_tokens']} tokenov)")
    else:
        print(f"   Thinking: Vypnutý")
    
    print(f"   Výstupný súbor: {output_file}")
    print()
        
    # Process the transcript
    processor = TranscriptProcessor(config)
    try:
        transcript = processor.read_transcript(transcript_path)
        print(f"📊 Veľkosť transkriptu: {len(transcript)} znakov")
        processor.process_transcript(transcript, output_file)
    except Exception as e:
        print(f"❌ Chyba: {str(e)}")


if __name__ == "__main__":
    main()