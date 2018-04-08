import { Component, OnInit, Input } from '@angular/core';
import { ChatService } from '../../services/chat.service';
import { FormBuilder, FormGroup } from '@angular/forms';

@Component({
  // tslint:disable-next-line:component-selector
  selector: 'app-chat',
  templateUrl: './chat.component.html',
  styleUrls: ['./chat.component.scss']
})
export class ChatComponent implements OnInit {
  chatInitial;
  chatCurrent;
  chats = [];
  prettyChatCurrent;

  chatForm: FormGroup;
  chatFormFields: any;

  constructor(
    public fb: FormBuilder,
    public chatService: ChatService) {

    this.chatFormFields = {
      input: [''],
    };
    this.chatForm = this.fb.group(this.chatFormFields);

  }

  ngOnInit() {
    this.chatInitial = {
      'currentNode': '',
      'complete': null, 'context': {},
      'parameters': [],
      'extractedParameters': {},
      'speechResponse': '',
      'intent': {},
      'input': 'init_conversation',
      'missingParameters': []
    };

    this.chatService.converse(this.chatInitial)
      .then((c: any) => {
        c.owner = 'chat';
        this.changeCurrent(c);
      });
  }

  changeCurrent(c) {
    c.date = new Date();
    this.chats.push(c);
    this.chatCurrent = c;
    this.prettyChatCurrent = JSON ? JSON.stringify(c, null, '  ') : 'your browser doesnt support JSON so cant pretty print';
  }

  send() {
    const form = this.chatForm.value;
    const sendMessage = {
      ... this.chatCurrent,
      input: form.input,
      owner: 'user'
    };
    this.changeCurrent(sendMessage);
    this.chatService.converse(sendMessage)
      .then((c: any) => {
        c.owner = 'chat';
        this.changeCurrent(c);
        this.chatForm.reset();
      });

  }

}
